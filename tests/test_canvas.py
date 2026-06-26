"""canvas 모듈 테스트 — 순수 코어(markdown/payload) + create_canvas(fake client).

slack_sdk 미의존. Slack 실호출 없이 canvases.create 페이로드/응답 처리를 검증한다.
실 호출 검증은 스파이크(scratchpad canvas_spike.py, 2026-06-26 통과)로 별도 확인됨.
"""

from __future__ import annotations

from typing import Any

from app.canvas import (
    CANVAS_CREATE_METHOD,
    build_create_payload,
    create_canvas,
    postmortem_markdown,
)


def test_postmortem_markdown_has_title_diagnosis_and_checklist() -> None:
    md = postmortem_markdown(
        "checkout-service",
        "p99 breached 1200ms on the checkout path.",
        action_items=["bump memory limit", "add retry budget alarm"],
    )
    assert md.startswith("# Incident Postmortem — checkout-service")
    assert "## Diagnosis" in md
    assert "p99 breached 1200ms" in md
    # action items 는 Canvas 체크리스트로 렌더.
    assert "- [ ] bump memory limit" in md
    assert "- [ ] add retry budget alarm" in md


def test_postmortem_markdown_omits_action_section_when_empty() -> None:
    md = postmortem_markdown("api", "looks fine")
    assert "## Action items" not in md
    assert "looks fine" in md


def test_build_create_payload_includes_markdown_and_channel() -> None:
    payload = build_create_payload("T", "# hi", channel_id="C1")
    assert payload["title"] == "T"
    assert payload["document_content"] == {"type": "markdown", "markdown": "# hi"}
    assert payload["channel_id"] == "C1"


def test_build_create_payload_omits_channel_when_none() -> None:
    payload = build_create_payload("T", "# hi", channel_id=None)
    assert "channel_id" not in payload


class _FakeClient:
    def __init__(self, resp: dict[str, Any] | None = None, raises: Exception | None = None) -> None:
        self._resp = resp or {"ok": True, "canvas_id": "F123"}
        self._raises = raises
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def api_call(self, method: str, *, json: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((method, json))
        if self._raises is not None:
            raise self._raises
        return self._resp


def test_create_canvas_returns_canvas_id_and_calls_method() -> None:
    client = _FakeClient()
    cid = create_canvas(client, title="T", markdown="# hi", channel_id="C1")
    assert cid == "F123"
    method, payload = client.calls[0]
    assert method == CANVAS_CREATE_METHOD
    assert payload["channel_id"] == "C1"


def test_create_canvas_returns_none_on_api_error() -> None:
    client = _FakeClient(raises=RuntimeError("missing_scope"))
    assert create_canvas(client, title="T", markdown="x", channel_id="C1") is None


def test_create_canvas_returns_none_when_no_canvas_id() -> None:
    client = _FakeClient(resp={"ok": False})
    assert create_canvas(client, title="T", markdown="x") is None
