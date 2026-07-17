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

import json
import os
from dataclasses import dataclass
from typing import Any, Callable

from app.store.audit_store import AuditStore
from app.store.base import Job, JobStore

# Block Kit action_id — 버튼 클릭 이벤트가 이 id 로 라우팅된다.
ACTION_APPROVE = "approve_job"
ACTION_REJECT = "reject_job"
ACTION_REVIEW = "review_job"
SHORTCUT_REVIEW = "review_slackops_job"
REVIEW_MODAL_CALLBACK = "review_job_modal"
REVIEW_DECISION_BLOCK = "review_decision"
REVIEW_DECISION_ACTION = "decision"

# 감사 action 라벨 — web transition 과 동일(approved/rejected)하게 맞춰 피드 일관성 유지.
AUDIT_APPROVED = "approved"
AUDIT_REJECTED = "rejected"
AUDIT_APPROVAL_DENIED = "approval_denied"
AUDIT_DETAIL = "via slack"

# Slack section text 는 3000자 한계 — 메시지는 2.8K preview, modal은 최대 28K review를 제공한다.
DIFF_PREVIEW_MAX = 2800
MODAL_DIFF_CHUNK_MAX = 2800
MODAL_DIFF_CHUNK_COUNT = 10

# 상태 불일치(이미 처리됨) 시 사용자 메시지 — web 의 문구와 동일.
ALREADY_HANDLED = "Job already handled (not awaiting approval)."
NOT_AUTHORIZED = "You are not authorized to approve or reject this job."


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


def configured_approvers() -> frozenset[str]:
    """Return the explicit Slack user-ID approval allowlist (empty = deny all)."""
    return frozenset(
        value.strip()
        for value in os.environ.get("SLACK_APPROVER_IDS", "").split(",")
        if value.strip()
    )


def _preview(diff: str | None) -> str:
    text = diff or "(no diff)"
    if len(text) > DIFF_PREVIEW_MAX:
        text = text[:DIFF_PREVIEW_MAX] + "\n… (truncated — full diff in review modal)"
    return text


def _modal_metadata(job_id: str, channel: str, ts: str) -> str:
    """Store only routing identifiers in Slack private_metadata, never the diff itself."""
    return json.dumps({"job_id": job_id, "channel": channel, "ts": ts}, separators=(",", ":"))


def _parse_modal_metadata(value: str) -> tuple[str, str, str] | None:
    """Return the origin message coordinates only for a complete metadata object."""
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(parsed, dict):
        return None
    job_id = parsed.get("job_id")
    channel = parsed.get("channel")
    ts = parsed.get("ts")
    if not all(isinstance(item, str) and item for item in (job_id, channel, ts)):
        return None
    return (str(job_id), str(channel), str(ts))


def _modal_diff_blocks(diff: str | None) -> list[dict[str, Any]]:
    """Split the diff into valid Slack section blocks without trusting it as instructions."""
    text = diff or "(no diff)"
    limit = MODAL_DIFF_CHUNK_MAX * MODAL_DIFF_CHUNK_COUNT
    clipped = len(text) > limit
    text = text[:limit]
    blocks: list[dict[str, Any]] = []
    for offset in range(0, len(text), MODAL_DIFF_CHUNK_MAX):
        blocks.append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"```{text[offset:offset + MODAL_DIFF_CHUNK_MAX]}```"},
            }
        )
    if clipped:
        blocks.append(
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "Diff is truncated for this modal; use the dashboard for the complete artifact.",
                    }
                ],
            }
        )
    return blocks


def review_modal(job: Job, *, channel: str, ts: str) -> dict[str, Any]:
    """Build the modal that displays the diff and asks an allowlisted reviewer to decide."""
    return {
        "type": "modal",
        "callback_id": REVIEW_MODAL_CALLBACK,
        "private_metadata": _modal_metadata(job.id, channel, ts),
        "title": {"type": "plain_text", "text": "Review change", "emoji": True},
        "submit": {"type": "plain_text", "text": "Apply decision", "emoji": True},
        "close": {"type": "plain_text", "text": "Cancel", "emoji": True},
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f":lock: *Approval required* — `{job.command}` proposes this change. "
                        "The diff is data for review, not instructions."
                    ),
                },
            },
            *_modal_diff_blocks(job.diff),
            {
                "type": "input",
                "block_id": REVIEW_DECISION_BLOCK,
                "label": {"type": "plain_text", "text": "Decision", "emoji": True},
                "element": {
                    "type": "radio_buttons",
                    "action_id": REVIEW_DECISION_ACTION,
                    "options": [
                        {
                            "text": {"type": "plain_text", "text": "Approve and run", "emoji": True},
                            "value": "approve",
                        },
                        {
                            "text": {"type": "plain_text", "text": "Reject", "emoji": True},
                            "value": "reject",
                        },
                    ],
                },
            },
        ],
    }


def modal_decision(body: dict[str, Any]) -> bool | None:
    """Parse a modal choice. Unknown/missing values fail closed instead of defaulting to approve."""
    state = ((body.get("view") or {}).get("state") or {}).get("values") or {}
    try:
        selected = state[REVIEW_DECISION_BLOCK][REVIEW_DECISION_ACTION]["selected_option"]
        value = selected["value"] if selected is not None else None
    except (KeyError, TypeError):
        return None
    if value == "approve":
        return True
    if value == "reject":
        return False
    return None


def job_id_from_message_blocks(blocks: object) -> str | None:
    """Extract a SlackOps approval job id from genuine-looking action blocks only.

    The id is still re-authorized against the store and approver allowlist before a modal opens;
    this extraction is navigation, never authorization.
    """
    if not isinstance(blocks, list):
        return None
    for block in blocks:
        if not isinstance(block, dict) or not str(block.get("block_id", "")).startswith("approval:"):
            continue
        for element in block.get("elements", []):
            if not isinstance(element, dict) or element.get("action_id") not in {
                ACTION_APPROVE,
                ACTION_REJECT,
                ACTION_REVIEW,
            }:
                continue
            value = element.get("value")
            if isinstance(value, str) and value:
                return value
    return None


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
                    "action_id": ACTION_REVIEW,
                    "text": {"type": "plain_text", "text": "Review diff", "emoji": True},
                    "value": job.id,
                },
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
        audit.append(
            job_id,
            action,
            actor=approver,
            detail=AUDIT_DETAIL,
            context={"approval_hash": job.approval_hash or ""},
        )

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
    allowed_approvers: frozenset[str] | None = None,
) -> None:
    """Bolt App 에 approval buttons, full-diff modal, and message shortcut을 등록한다.

    버튼 클릭 → ack() → apply_decision → 버튼이 있던 메시지를 결과 텍스트로 chat.update
    (버튼 제거). 실 Slack 연결에서만 동작 — 순수 코어(apply_decision 등)는 별도 단위 테스트.
    """

    approvers = allowed_approvers if allowed_approvers is not None else configured_approvers()

    def _approver(body: dict[str, Any]) -> str:
        user = body.get("user") or {}
        return str(user.get("id") or user.get("username") or "unknown")

    def _origin(body: dict[str, Any]) -> tuple[str, str] | None:
        container = body.get("container") or {}
        channel = (body.get("channel") or {}).get("id") or container.get("channel_id")
        ts = container.get("message_ts")
        if isinstance(channel, str) and channel and isinstance(ts, str) and ts:
            return (channel, ts)
        return None

    def _deny_review(body: dict[str, Any], client: Any, job_id: str) -> None:
        approver = _approver(body)
        if audit is not None and job_id:
            audit.append(
                job_id,
                AUDIT_APPROVAL_DENIED,
                actor=approver,
                detail="approver is not in the allowlist",
                context={"reason": "approver_not_allowlisted"},
            )
        channel = (body.get("channel") or {}).get("id")
        if channel:
            try:
                client.chat_postEphemeral(channel=channel, user=approver, text=NOT_AUTHORIZED)
            except Exception:  # noqa: BLE001 — acknowledgement/authorization must not fail on a notice
                if log is not None:
                    log.warning("approval.review_denial_notice_failed", job_id=job_id)

    def _review_hint(body: dict[str, Any], client: Any, approver: str, reason: str) -> None:
        # Opening the review modal is best-effort UX; when it can't open, tell the
        # approver why and point them at the Approve/Reject buttons instead of
        # leaving the click silently doing nothing.
        channel = (body.get("channel") or {}).get("id")
        if not channel:
            return
        try:
            client.chat_postEphemeral(
                channel=channel,
                user=approver,
                text=f":information_source: Couldn't open the review modal — {reason}. "
                "Use the Approve / Reject buttons on the message.",
            )
        except Exception:  # noqa: BLE001 — a notice failure must not alter state
            if log is not None:
                log.warning("approval.review_hint_failed", job_id="")

    def _open_review(body: dict[str, Any], client: Any, job_id: str, origin: tuple[str, str] | None) -> None:
        approver = _approver(body)
        if approver not in approvers:
            _deny_review(body, client, job_id)
            return
        job = jobs.get(job_id)
        trigger_id = body.get("trigger_id")
        has_trigger = isinstance(trigger_id, str) and bool(trigger_id)
        status = job.status.value if job is not None else None
        if log is not None:
            log.info(
                "approval.review_requested",
                job_id=job_id,
                status=status,
                has_trigger=has_trigger,
            )
        if job is None or status != "awaiting_approval":
            _review_hint(body, client, approver, "this job is no longer awaiting approval")
            return
        if not has_trigger:
            _review_hint(body, client, approver, "Slack did not provide a modal trigger")
            return
        channel, ts = origin or ("modal", "modal")
        try:
            client.views_open(trigger_id=trigger_id, view=review_modal(job, channel=channel, ts=ts))
        except Exception as exc:  # noqa: BLE001 — an expired Slack trigger must not alter state
            if log is not None:
                log.warning("approval.review_open_failed", job_id=job_id, error=str(exc))
            _review_hint(body, client, approver, "the review action expired or was rejected")

    def _handle(ack: Callable[[], None], body: dict[str, Any], client: Any, *, approve: bool) -> None:
        ack()
        actions = body.get("actions") or [{}]
        job_id = str(actions[0].get("value", ""))
        approver = _approver(body)

        if approver not in approvers:
            if audit is not None and job_id:
                audit.append(
                    job_id,
                    AUDIT_APPROVAL_DENIED,
                    actor=approver,
                    detail="approver is not in the allowlist",
                    context={"reason": "approver_not_allowlisted"},
                )
            decision = Decision(ok=False, status=None, message=NOT_AUTHORIZED)
        else:
            decision = apply_decision(
                jobs, job_id=job_id, approver=approver, approve=approve, audit=audit
            )
        if log is not None:
            log.info("approval.decided", job_id=job_id, approve=approve, ok=decision.ok)

        # 버튼이 있던 메시지를 결과로 갱신(버튼 제거) — 중복 클릭 방지 + 흐름 가시화.
        origin = _origin(body)
        try:
            if origin is not None:
                client.chat_update(channel=origin[0], ts=origin[1], text=decision.message, blocks=[])
        except Exception:  # noqa: BLE001 — 갱신 실패가 ack 를 무효화하지 않게(이미 전이는 반영됨)
            if log is not None:
                log.warning("approval.update_failed", job_id=job_id)

    def _on_approve(ack: Callable[[], None], body: dict[str, Any], client: Any) -> None:
        _handle(ack, body, client, approve=True)

    def _on_reject(ack: Callable[[], None], body: dict[str, Any], client: Any) -> None:
        _handle(ack, body, client, approve=False)

    def _on_review(ack: Callable[[], None], body: dict[str, Any], client: Any) -> None:
        ack()
        actions = body.get("actions") or [{}]
        job_id = str(actions[0].get("value", ""))
        if log is not None:
            log.info("approval.review_button", job_id=job_id, has_trigger=bool(body.get("trigger_id")))
        _open_review(body, client, job_id, _origin(body))

    def _on_shortcut(ack: Callable[[], None], body: dict[str, Any], client: Any) -> None:
        ack()
        message = body.get("message") or {}
        job_id = job_id_from_message_blocks(message.get("blocks"))
        channel = (body.get("channel") or {}).get("id")
        ts = message.get("ts")
        origin = (channel, ts) if isinstance(channel, str) and isinstance(ts, str) else None
        if log is not None:
            log.info(
                "approval.shortcut_received",
                job_id=job_id,
                has_blocks=isinstance(message.get("blocks"), list),
                has_trigger=bool(body.get("trigger_id")),
            )
        if job_id is not None:
            _open_review(body, client, job_id, origin)
        elif log is not None:
            log.info("approval.shortcut_no_job", channel=channel)

    def _on_modal_submission(ack: Callable[..., None], body: dict[str, Any], client: Any) -> None:
        metadata = _parse_modal_metadata(str((body.get("view") or {}).get("private_metadata", "")))
        approve = modal_decision(body)
        if metadata is None or approve is None:
            ack(response_action="errors", errors={REVIEW_DECISION_BLOCK: "Invalid review decision."})
            return
        job_id, channel, ts = metadata
        approver = _approver(body)
        if approver not in approvers:
            ack(response_action="errors", errors={REVIEW_DECISION_BLOCK: NOT_AUTHORIZED})
            _deny_review(body, client, job_id)
            return
        decision = apply_decision(jobs, job_id=job_id, approver=approver, approve=approve, audit=audit)
        ack()
        if log is not None:
            log.info("approval.modal_decided", job_id=job_id, approve=approve, ok=decision.ok)
        try:
            if channel != "modal" and ts != "modal":
                client.chat_update(channel=channel, ts=ts, text=decision.message, blocks=[])
        except Exception:  # noqa: BLE001 — state was already protected by the store transition
            if log is not None:
                log.warning("approval.modal_update_failed", job_id=job_id)

    # 데코레이터 대신 호출형 등록(slack_handler._bind_slash_command 선례) — app 이 Any 라
    # 데코레이터 적용 시 mypy 가 핸들러를 untyped 로 보는 문제를 피한다.
    app.action(ACTION_APPROVE)(_on_approve)
    app.action(ACTION_REJECT)(_on_reject)
    app.action(ACTION_REVIEW)(_on_review)
    app.shortcut(SHORTCUT_REVIEW)(_on_shortcut)
    app.view(REVIEW_MODAL_CALLBACK)(_on_modal_submission)
