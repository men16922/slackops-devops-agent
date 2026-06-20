"""proposal_notifier 테스트 — 순수 notify_new_proposals + run_forever (Slack SDK 불필요)."""

from __future__ import annotations

import pytest

from app.proposal_notifier import format_proposal, notify_new_proposals, run_forever
from app.store import Job, JobSource, JobStatus, SqliteJobStore
from tests._helpers import counter_clock, counter_id


@pytest.fixture
def store() -> SqliteJobStore:
    return SqliteJobStore(":memory:", clock=counter_clock(), id_factory=counter_id())


def _agent_job(
    store: SqliteJobStore,
    command: str = "diagnose",
    args: str = "api",
    rationale: str = "5xx",
) -> Job:
    return store.enqueue(
        command, args, source=JobSource.AGENT, requested_by="agent", rationale=rationale
    )


def test_notify_posts_for_open_agent_jobs_only(store: SqliteJobStore) -> None:
    a1 = _agent_job(store, "diagnose", "api")
    a2 = _agent_job(store, "logs", "web")
    store.enqueue("diagnose", "x", source=JobSource.WEB)  # 사람 작업 — 알림 제외
    posts: list[str] = []
    seen: set[str] = set()
    newly = notify_new_proposals(store, posts.append, seen)
    assert set(newly) == {a1.id, a2.id}
    assert len(posts) == 2
    assert seen == {a1.id, a2.id}


def test_notify_dedupes_via_seen(store: SqliteJobStore) -> None:
    _agent_job(store)
    posts: list[str] = []
    seen: set[str] = set()
    notify_new_proposals(store, posts.append, seen)
    second = notify_new_proposals(store, posts.append, seen)
    assert second == []
    assert len(posts) == 1


def test_notify_skips_terminal(store: SqliteJobStore) -> None:
    job = _agent_job(store)
    store.claim()  # pending → running
    store.complete(job.id, status=JobStatus.DONE)
    posts: list[str] = []
    assert notify_new_proposals(store, posts.append, set()) == []
    assert posts == []


def test_notify_posts_chronological(store: SqliteJobStore) -> None:
    """list_recent 최신순을 reversed 해 오래된 제안 먼저 게시."""
    _agent_job(store, "diagnose", "first")
    _agent_job(store, "diagnose", "second")
    posts: list[str] = []
    notify_new_proposals(store, posts.append, set())
    assert "first" in posts[0]
    assert "second" in posts[1]


def test_format_proposal_with_dashboard_url(
    store: SqliteJobStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DASHBOARD_URL", "https://app.example.com/")
    job = _agent_job(store, "diagnose", "api", "5xx spike")
    text = format_proposal(job)
    assert "diagnose" in text
    assert "5xx spike" in text
    assert f"https://app.example.com/jobs/{job.id}" in text


def test_format_proposal_without_dashboard_url(
    store: SqliteJobStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("DASHBOARD_URL", raising=False)
    job = _agent_job(store)
    assert f"(job {job.id})" in format_proposal(job)


def test_run_forever_sleeps_and_dedupes(store: SqliteJobStore) -> None:
    _agent_job(store)
    posts: list[str] = []
    sleeps: list[float] = []
    posted = run_forever(store, posts.append, max_iterations=3, sleep=sleeps.append)
    assert posted == 1  # 첫 주기만 게시, 이후 dedupe
    assert len(posts) == 1
    assert len(sleeps) == 3  # 매 주기 sleep 주입 호출


def test_post_failure_leaves_id_unseen(store: SqliteJobStore) -> None:
    job = _agent_job(store)
    seen: set[str] = set()

    def boom(_text: str) -> None:
        raise RuntimeError("rate limited")

    assert notify_new_proposals(store, boom, seen) == []
    assert job.id not in seen  # 다음 주기 재시도 가능
