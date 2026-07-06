"""Slack Canvas 포스트모템 — 진단 결과를 채널 탭 Canvas(런북/포스트모템 산출물)로 게시.

`canvases.create`(scope `canvases:write`)로 markdown content 를 생성한다. Free 팀은 standalone
canvas 불가 → `channel_id` 로 **채널 탭 canvas** 를 만든다(스파이크 2026-06-26 검증: canvas_id 반환).
markdown 은 표·h1-3·코드블록·체크리스트·divider 를 지원 → 포스트모템/액션아이템에 적합.

설계(approval_actions 와 동일 철학):
- **순수 코어**(slack_sdk 미의존 — 단위 테스트 가능): postmortem_markdown / build_create_payload.
- **Slack 바인딩**(create_canvas): client.api_call("canvases.create", …) 호출 → canvas_id 반환.
"""

from __future__ import annotations

from typing import Any

# Slack Web API method + 생성에 필요한 봇 스코프(앱에 사전 부여 필요).
CANVAS_CREATE_METHOD = "canvases.create"
CANVAS_SCOPE = "canvases:write"


def postmortem_markdown(
    service: str,
    diagnosis: str,
    *,
    action_items: list[str] | None = None,
) -> str:
    """진단 텍스트를 포스트모템 Canvas markdown 으로 감싼다.

    Args:
        service: 대상 서비스명(제목/헤딩에 사용).
        diagnosis: 에이전트 진단 본문(Slack mrkdwn/markdown 그대로 삽입).
        action_items: 후속 조치 — 체크리스트로 렌더(없으면 섹션 생략).

    Returns:
        canvases.create 의 document_content.markdown 에 넣을 문자열.
    """
    lines = [
        f"# Incident Postmortem — {service}",
        "",
        "> Auto-drafted by the SlackOps agent. Review and edit before sharing.",
        "",
        "## Diagnosis",
        diagnosis.strip() or "_(no diagnosis text)_",
        "",
    ]
    if action_items:
        lines.append("## Action items")
        lines.extend(f"- [ ] {item}" for item in action_items)
        lines.append("")
    return "\n".join(lines)


def build_create_payload(
    title: str,
    markdown: str,
    *,
    channel_id: str | None = None,
) -> dict[str, Any]:
    """canvases.create 요청 본문 구성.

    channel_id 가 있으면 채널 탭 canvas(Free 팀 필수). 없으면 standalone(유료 팀만).
    """
    payload: dict[str, Any] = {
        "title": title,
        "document_content": {"type": "markdown", "markdown": markdown},
    }
    if channel_id:
        payload["channel_id"] = channel_id
    return payload


def create_canvas(
    client: Any,
    *,
    title: str,
    markdown: str,
    channel_id: str | None = None,
    log: Any | None = None,
) -> str | None:
    """채널 탭 Canvas 를 생성하고 canvas_id 를 반환(실패 시 None).

    client 는 Slack WebClient(또는 호환). 스코프 미부여/플랜 미지원 등 실패는 None 으로
    흡수해 호출 흐름(스레드 응답)을 막지 않는다 — Canvas 는 부가 산출물이다.
    """
    payload = build_create_payload(title, markdown, channel_id=channel_id)
    try:
        resp = client.api_call(CANVAS_CREATE_METHOD, json=payload)
    except Exception as exc:  # noqa: BLE001 — Canvas 실패가 진단 응답을 막지 않게.
        if log is not None:
            log.warning("canvas.create_failed", error=str(exc))
        return None
    canvas_id = resp.get("canvas_id") if hasattr(resp, "get") else None
    if log is not None:
        log.info("canvas.created", canvas_id=canvas_id, channel=channel_id)
    return str(canvas_id) if canvas_id else None
