"""Slack in-thread 승인 게이트 — AWAITING_APPROVAL job 을 Slack 버튼으로 승인/거부.

web 대시보드 Approve/Reject(`web/app/actions.ts:transition`)와 **동일한 상태머신**을 재사용:
`store.approve/reject`(ConditionExpression status=awaiting_approval 낙관락) + audit append.
새 상태 없음 — Slack 버튼은 같은 출력 게이트의 또 다른 입력 표면일 뿐이다(이중 컨트롤플레인).

설계(assistant_handler 와 동일 철학):
- **순수 코어**(slack_bolt 미의존 — import-safe·단위 테스트 가능): decision_blocks /
  apply_decision / Decision + 상수. store/audit 는 주입 — 실 Slack/DynamoDB 없이 테스트.
- **Bolt 바인딩**(register_approval_actions): slack_bolt 를 lazy import 해 @app.action 핸들러를
  등록. 버튼 클릭 → apply_decision → 버튼이 있던 메시지를 chat.update 로 결과 표기.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from app.store.audit_store import AuditStore
from app.store.base import Job, JobStore

# Block Kit action_id — 버튼 클릭 이벤트가 이 id 로 라우팅된다.
ACTION_APPROVE = "approve_job"
ACTION_REJECT = "reject_job"

# 감사 action 라벨 — web transition 과 동일(approved/rejected)하게 맞춰 피드 일관성 유지.
AUDIT_APPROVED = "approved"
AUDIT_REJECTED = "rejected"
AUDIT_DETAIL = "via slack"

# Slack section text 는 3000자 한계 — diff 미리보기는 그 아래로 자른다(전체는 Modal=D2.5).
DIFF_PREVIEW_MAX = 2800

# 상태 불일치(이미 처리됨) 시 사용자 메시지 — web 의 문구와 동일.
ALREADY_HANDLED = "Job already handled (not awaiting approval)."


@dataclass
class Decision:
    """승인/거부 적용 결과 — Bolt 바인딩이 그대로 chat.update 에 쓸 수 있게 메시지를 담는다.

    Attributes:
        ok: 상태 전이 성공 여부(False = 이미 처리된 job).
        status: 성공 시 새 상태값(approved|rejected), 실패면 None.
        message: Slack 게시용 텍스트(성공/실패 모두 채워짐).
    """

    ok: bool
    status: str | None
    message: str


def _preview(diff: str | None) -> str:
    text = diff or "(no diff)"
    if len(text) > DIFF_PREVIEW_MAX:
        text = text[:DIFF_PREVIEW_MAX] + "\n… (truncated — full diff in review modal)"
    return text


def decision_blocks(job: Job) -> list[dict[str, Any]]:
    """AWAITING_APPROVAL job 에 대한 diff 미리보기 + Approve/Reject 버튼 블록.

    버튼 value 에 job_id 를 실어 클릭 핸들러가 대상 job 을 식별한다.
    """
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f":lock: *Approval required* — `{job.command}` proposes a change. Review the diff:",
            },
        },
        {"type": "section", "text": {"type": "mrkdwn", "text": f"```{_preview(job.diff)}```"}},
        {
            "type": "actions",
            "block_id": f"approval:{job.id}",
            "elements": [
                {
                    "type": "button",
                    "action_id": ACTION_APPROVE,
                    "style": "primary",
                    "text": {"type": "plain_text", "text": "✅ Approve", "emoji": True},
                    "value": job.id,
                },
                {
                    "type": "button",
                    "action_id": ACTION_REJECT,
                    "style": "danger",
                    "text": {"type": "plain_text", "text": "❌ Reject", "emoji": True},
                    "value": job.id,
                },
            ],
        },
    ]


def apply_decision(
    jobs: JobStore,
    *,
    job_id: str,
    approver: str,
    approve: bool,
    audit: AuditStore | None = None,
) -> Decision:
    """승인/거부를 store 에 적용(+선택 audit) — web transition 미러.

    store.approve/reject 는 상태 불일치(이미 처리/만료)면 None 을 돌려준다(낙관락) →
    멱등: 두 사람이 동시에 눌러도 한 번만 전이되고 나머지는 ALREADY_HANDLED.

    Args:
        jobs: JobStore(주입).
        job_id: 버튼 value 의 대상 job.
        approver: 행위자 식별자(Slack user id) — 감사 actor + 멘션에 사용.
        approve: True=승인, False=거부.
        audit: AuditStore(주입, 선택). None 이면 감사 생략(상태 전이는 그대로).

    Returns:
        Decision(ok, status, message).
    """
    job = jobs.approve(job_id, approver) if approve else jobs.reject(job_id, approver)
    if job is None:
        return Decision(ok=False, status=None, message=ALREADY_HANDLED)

    action = AUDIT_APPROVED if approve else AUDIT_REJECTED
    if audit is not None:
        audit.append(job_id, action, actor=approver, detail=AUDIT_DETAIL)

    if approve:
        message = f":white_check_mark: `{job.command}` approved by <@{approver}> — running now."
    else:
        message = f":x: `{job.command}` rejected by <@{approver}> — discarded."
    return Decision(ok=True, status=job.status.value, message=message)


def register_approval_actions(
    app: Any,
    *,
    jobs: JobStore,
    audit: AuditStore | None = None,
    log: Any | None = None,
) -> None:
    """Bolt App 에 Approve/Reject 버튼 핸들러를 등록(slash command·Assistant 와 공존).

    버튼 클릭 → ack() → apply_decision → 버튼이 있던 메시지를 결과 텍스트로 chat.update
    (버튼 제거). 실 Slack 연결에서만 동작 — 순수 코어(apply_decision 등)는 별도 단위 테스트.
    """

    def _handle(ack: Callable[[], None], body: dict[str, Any], client: Any, *, approve: bool) -> None:
        ack()
        actions = body.get("actions") or [{}]
        job_id = str(actions[0].get("value", ""))
        user = body.get("user") or {}
        approver = str(user.get("id") or user.get("username") or "unknown")

        decision = apply_decision(jobs, job_id=job_id, approver=approver, approve=approve, audit=audit)
        if log is not None:
            log.info("approval.decided", job_id=job_id, approve=approve, ok=decision.ok)

        # 버튼이 있던 메시지를 결과로 갱신(버튼 제거) — 중복 클릭 방지 + 흐름 가시화.
        container = body.get("container") or {}
        channel = (body.get("channel") or {}).get("id") or container.get("channel_id")
        ts = container.get("message_ts")
        try:
            if channel and ts:
                client.chat_update(channel=channel, ts=ts, text=decision.message, blocks=[])
        except Exception:  # noqa: BLE001 — 갱신 실패가 ack 를 무효화하지 않게(이미 전이는 반영됨)
            if log is not None:
                log.warning("approval.update_failed", job_id=job_id)

    def _on_approve(ack: Callable[[], None], body: dict[str, Any], client: Any) -> None:
        _handle(ack, body, client, approve=True)

    def _on_reject(ack: Callable[[], None], body: dict[str, Any], client: Any) -> None:
        _handle(ack, body, client, approve=False)

    # 데코레이터 대신 호출형 등록(slack_handler._bind_slash_command 선례) — app 이 Any 라
    # 데코레이터 적용 시 mypy 가 핸들러를 untyped 로 보는 문제를 피한다.
    app.action(ACTION_APPROVE)(_on_approve)
    app.action(ACTION_REJECT)(_on_reject)
