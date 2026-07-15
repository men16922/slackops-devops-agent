"""approval_actions 순수 코어 테스트 — slack_bolt 미의존.

decision_blocks(버튼/diff 미리보기), apply_decision(승인/거부 store 전이 + audit +
멱등), Decision 메시지를 in-memory Sqlite store 로 검증한다. Bolt 바인딩
(register_approval_actions)은 실 Slack 에서만 동작하므로 여기서 다루지 않는다.
"""

from __future__ import annotations

from typing import Any

from app.approval_actions import (
    ACTION_APPROVE,
    ACTION_REJECT,
    ALREADY_HANDLED,
    AUDIT_APPROVED,
    AUDIT_APPROVAL_DENIED,
    AUDIT_REJECTED,
    DIFF_PREVIEW_MAX,
    NOT_AUTHORIZED,
    apply_decision,
    decision_blocks,
    register_approval_actions,
)
from app.store.audit_store import SqliteAuditStore
from app.store.base import JobSource, JobStatus
from app.store.sqlite_store import SqliteJobStore


def _awaiting_job(store: SqliteJobStore, *, command: str = "pr", diff: str = "diff --git a b") -> str:
    """PENDING → claim(RUNNING) → await_approval(AWAITING_APPROVAL) job 을 만들고 id 반환."""
    job = store.enqueue(command, "bump memory", source=JobSource.AGENT, requested_by="agent")
    store.claim()
    store.await_approval(
        job.id,
        diff,
        execution_plan="{\"test\":true}",
        execution_plan_hash="test-plan-hash",
    )
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


# ── Bolt 바인딩 테스트 (fake app/client — slack_bolt 미의존) ─────────────


class _FakeApp:
    """app.action(id)(fn) 등록을 잡아두는 최소 Bolt App 대역."""

    def __init__(self) -> None:
        self.handlers: dict[str, Any] = {}

    def action(self, action_id: str) -> Any:
        def _register(fn: Any) -> Any:
            self.handlers[action_id] = fn
            return fn

        return _register


class _FakeClient:
    def __init__(self) -> None:
        self.updates: list[dict[str, Any]] = []

    def chat_update(self, **kwargs: Any) -> None:
        self.updates.append(kwargs)


def _body(job_id: str) -> dict[str, Any]:
    return {
        "actions": [{"value": job_id}],
        "user": {"id": "U777"},
        "container": {"message_ts": "1700.5"},
        "channel": {"id": "C1"},
    }


def test_binding_approve_transitions_and_updates_message() -> None:
    store = SqliteJobStore()
    audit = SqliteAuditStore()
    job_id = _awaiting_job(store)
    app = _FakeApp()
    register_approval_actions(app, jobs=store, audit=audit, allowed_approvers=frozenset({"U777"}))
    client = _FakeClient()

    app.handlers[ACTION_APPROVE](ack=lambda: None, body=_body(job_id), client=client)

    assert store.get(job_id).status is JobStatus.APPROVED  # type: ignore[union-attr]
    assert audit.list_for_job(job_id)[-1].action == AUDIT_APPROVED
    # 버튼이 있던 메시지를 결과 텍스트로 갱신(버튼 제거).
    assert client.updates and client.updates[0]["channel"] == "C1"
    assert client.updates[0]["ts"] == "1700.5"
    assert "approved" in client.updates[0]["text"]
    assert client.updates[0]["blocks"] == []


def test_binding_reject_routes_to_reject() -> None:
    store = SqliteJobStore()
    job_id = _awaiting_job(store)
    app = _FakeApp()
    register_approval_actions(app, jobs=store, allowed_approvers=frozenset({"U777"}))
    client = _FakeClient()

    app.handlers[ACTION_REJECT](ack=lambda: None, body=_body(job_id), client=client)

    assert store.get(job_id).status is JobStatus.REJECTED  # type: ignore[union-attr]


def test_binding_registers_both_action_ids() -> None:
    app = _FakeApp()
    register_approval_actions(app, jobs=SqliteJobStore())
    assert set(app.handlers) == {ACTION_APPROVE, ACTION_REJECT}


def test_binding_denies_user_outside_approver_allowlist() -> None:
    store = SqliteJobStore()
    audit = SqliteAuditStore()
    job_id = _awaiting_job(store)
    app = _FakeApp()
    register_approval_actions(
        app, jobs=store, audit=audit, allowed_approvers=frozenset({"U1"})
    )
    client = _FakeClient()

    app.handlers[ACTION_APPROVE](ack=lambda: None, body=_body(job_id), client=client)

    assert store.get(job_id).status is JobStatus.AWAITING_APPROVAL  # type: ignore[union-attr]
    assert client.updates[0]["text"] == NOT_AUTHORIZED
    [event] = audit.list_for_job(job_id)
    assert event.action == AUDIT_APPROVAL_DENIED
    assert event.actor == "U777"
    assert event.context == {"reason": "approver_not_allowlisted"}


def test_audit_labels_match_dashboard_feed_contract() -> None:
    # web/app/actions.ts transition 이 쓰는 라벨과 동일해야 피드/대시보드가 일관 — 드리프트 가드.
    assert AUDIT_APPROVED == "approved"
    assert AUDIT_REJECTED == "rejected"
