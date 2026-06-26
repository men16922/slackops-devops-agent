"""approval_actions 순수 코어 테스트 — slack_bolt 미의존.

decision_blocks(버튼/diff 미리보기), apply_decision(승인/거부 store 전이 + audit +
멱등), Decision 메시지를 in-memory Sqlite store 로 검증한다. Bolt 바인딩
(register_approval_actions)은 실 Slack 에서만 동작하므로 여기서 다루지 않는다.
"""

from __future__ import annotations

from app.approval_actions import (
    ACTION_APPROVE,
    ACTION_REJECT,
    ALREADY_HANDLED,
    AUDIT_APPROVED,
    AUDIT_REJECTED,
    DIFF_PREVIEW_MAX,
    apply_decision,
    decision_blocks,
)
from app.store.audit_store import SqliteAuditStore
from app.store.base import JobSource, JobStatus
from app.store.sqlite_store import SqliteJobStore


def _awaiting_job(store: SqliteJobStore, *, command: str = "pr", diff: str = "diff --git a b") -> str:
    """PENDING → claim(RUNNING) → await_approval(AWAITING_APPROVAL) job 을 만들고 id 반환."""
    job = store.enqueue(command, "bump memory", source=JobSource.AGENT, requested_by="agent")
    store.claim()
    store.await_approval(job.id, diff)
    return job.id


def test_decision_blocks_has_buttons_with_job_id_value() -> None:
    store = SqliteJobStore()
    job_id = _awaiting_job(store, diff="hello diff")
    job = store.get(job_id)
    assert job is not None

    blocks = decision_blocks(job)
    actions = [b for b in blocks if b["type"] == "actions"][0]
    ids = {e["action_id"]: e["value"] for e in actions["elements"]}
    assert ids == {ACTION_APPROVE: job_id, ACTION_REJECT: job_id}
    # diff 가 미리보기 섹션에 코드블록으로 들어간다.
    assert any("hello diff" in str(b) for b in blocks)


def test_decision_blocks_truncates_long_diff() -> None:
    store = SqliteJobStore()
    job_id = _awaiting_job(store, diff="x" * (DIFF_PREVIEW_MAX + 500))
    job = store.get(job_id)
    assert job is not None
    text = str(decision_blocks(job))
    assert "truncated" in text


def test_apply_decision_approve_transitions_and_audits() -> None:
    store = SqliteJobStore()
    audit = SqliteAuditStore()
    job_id = _awaiting_job(store)

    decision = apply_decision(store, job_id=job_id, approver="U123", approve=True, audit=audit)

    assert decision.ok is True
    assert decision.status == JobStatus.APPROVED.value
    assert "<@U123>" in decision.message
    assert store.get(job_id).status is JobStatus.APPROVED  # type: ignore[union-attr]
    events = audit.list_for_job(job_id)
    assert events[-1].action == AUDIT_APPROVED
    assert events[-1].actor == "U123"


def test_apply_decision_reject_transitions_and_audits() -> None:
    store = SqliteJobStore()
    audit = SqliteAuditStore()
    job_id = _awaiting_job(store)

    decision = apply_decision(store, job_id=job_id, approver="U9", approve=False, audit=audit)

    assert decision.ok is True
    assert decision.status == JobStatus.REJECTED.value
    assert store.get(job_id).status is JobStatus.REJECTED  # type: ignore[union-attr]
    assert audit.list_for_job(job_id)[-1].action == AUDIT_REJECTED


def test_apply_decision_is_idempotent_on_double_click() -> None:
    store = SqliteJobStore()
    job_id = _awaiting_job(store)

    first = apply_decision(store, job_id=job_id, approver="U1", approve=True)
    second = apply_decision(store, job_id=job_id, approver="U2", approve=True)

    assert first.ok is True
    assert second.ok is False
    assert second.message == ALREADY_HANDLED


def test_apply_decision_audit_optional() -> None:
    store = SqliteJobStore()
    job_id = _awaiting_job(store)
    # audit 미주입이어도 상태 전이는 성공한다.
    decision = apply_decision(store, job_id=job_id, approver="U1", approve=True, audit=None)
    assert decision.ok is True
    assert store.get(job_id).status is JobStatus.APPROVED  # type: ignore[union-attr]
