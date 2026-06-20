"""proposal_notifier 테스트 — 작업 생명주기 이벤트 알림(순수, Slack SDK 불필요)."""

from __future__ import annotations

import pytest

from app.proposal_notifier import notify_job_events, run_forever
from app.store import JobSource, JobStatus, SqliteJobStore
from tests._helpers import counter_clock, counter_id


@pytest.fixture
def store() -> SqliteJobStore:
    return SqliteJobStore(":memory:", clock=counter_clock(), id_factory=counter_id())


def test_new_web_job_notifies_queued(store: SqliteJobStore) -> None:
    job = store.enqueue("diagnose", "api", source=JobSource.WEB, requested_by="kim")
    posts: list[str] = []
    newly = notify_job_events(store, posts.append, {})
    assert newly == [job.id]
    assert "Queued" in posts[0]
    assert "kim" in posts[0]


def test_agent_pending_notifies_proposal(store: SqliteJobStore) -> None:
    store.enqueue(
        "diagnose", "api", source=JobSource.AGENT, requested_by="agent", rationale="5xx"
    )
    posts: list[str] = []
    notify_job_events(store, posts.append, {})
    assert "Agent proposal" in posts[0]
    assert "5xx" in posts[0]


def test_done_notifies_with_cost(store: SqliteJobStore) -> None:
    job = store.enqueue("diagnose", "api")
    store.claim()
    store.complete(job.id, status=JobStatus.DONE, cost_usd=0.1389, tokens=1759)
    posts: list[str] = []
    notify_job_events(store, posts.append, {})
    assert any("Done" in p and "0.1389" in p for p in posts)


def test_failed_notifies_error(store: SqliteJobStore) -> None:
    job = store.enqueue("pr", "x")
    store.claim()
    store.complete(job.id, status=JobStatus.FAILED, error="git push denied")
    posts: list[str] = []
    notify_job_events(store, posts.append, {})
    assert any("Failed" in p and "git push denied" in p for p in posts)


def test_awaiting_approval_notifies(store: SqliteJobStore) -> None:
    job = store.enqueue("pr", "bump timeout")
    store.claim()
    store.await_approval(job.id, "diff --git ...")
    posts: list[str] = []
    notify_job_events(store, posts.append, {})
    assert any("Awaiting approval" in p for p in posts)


def test_running_not_notified(store: SqliteJobStore) -> None:
    job = store.enqueue("diagnose", "api")
    store.claim()  # running — NOTIFY_STATUSES 밖
    posts: list[str] = []
    seen: dict[str, str] = {}
    notify_job_events(store, posts.append, seen)
    assert posts == []
    assert seen[job.id] == "running"


def test_prime_suppresses_then_notifies_transition(store: SqliteJobStore) -> None:
    job = store.enqueue("diagnose", "api", source=JobSource.WEB)
    posts: list[str] = []
    seen: dict[str, str] = {}
    notify_job_events(store, posts.append, seen, prime=True)  # 무게시 기록
    assert posts == []
    assert seen[job.id] == "pending"
    store.claim()
    store.complete(job.id, status=JobStatus.DONE)
    notify_job_events(store, posts.append, seen)  # done 전이 → 게시
    assert any("Done" in p for p in posts)


def test_no_repost_same_status(store: SqliteJobStore) -> None:
    store.enqueue("diagnose", "api", source=JobSource.WEB)
    posts: list[str] = []
    seen: dict[str, str] = {}
    notify_job_events(store, posts.append, seen)
    n = len(posts)
    notify_job_events(store, posts.append, seen)  # 상태 그대로 → 재게시 없음
    assert len(posts) == n


def test_post_failure_retries(store: SqliteJobStore) -> None:
    store.enqueue("diagnose", "api", source=JobSource.WEB)
    seen: dict[str, str] = {}
    calls = {"n": 0}

    def flaky(_text: str) -> None:
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("rate limited")

    notify_job_events(store, flaky, seen)  # 1st post raises → seen 미갱신
    notify_job_events(store, flaky, seen)  # 재시도 → 성공
    assert calls["n"] == 2


def test_run_forever_primes_first_iteration(store: SqliteJobStore) -> None:
    store.enqueue("diagnose", "api", source=JobSource.WEB)
    posts: list[str] = []
    sleeps: list[float] = []
    posted = run_forever(store, posts.append, max_iterations=3, sleep=sleeps.append)
    assert posted == 0  # prime(1회) 후 상태 변화 없음 → 게시 0
    assert posts == []
    assert len(sleeps) == 3
