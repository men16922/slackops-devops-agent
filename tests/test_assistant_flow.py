"""Assistant 종단 통합 검증 — run_user_message 를 fake Slack(say/client) + 실 store 로 구동.

실 Slack 없이 **바인딩 전체 흐름**(placeholder→스트리밍→제안→정착폴링→후속/버튼→Canvas)을
끝까지 돌려 배선 버그를 잡는다. propose_job MCP 는 우회하고(스트림이 job_id 만 흘림), worker 는
store 전이로 시뮬레이트한다. 버튼 클릭은 register_approval_actions 핸들러로 검증한다.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

from app.approval_actions import ACTION_APPROVE, register_approval_actions
from app.assistant_handler import run_user_message
from app.store.audit_store import SqliteAuditStore
from app.store.base import JobSource, JobStatus
from app.store.sqlite_store import SqliteJobStore


def _propose_stream(command: str, args: str, job_id: str, *, text: str = "Looking into it.") -> Any:
    lines = [
        json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}}),
        json.dumps(
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "mcp__slackops__propose_job",
                            "input": {"command": command, "args": args},
                        }
                    ]
                },
            }
        ),
        json.dumps(
            {
                "type": "user",
                "message": {
                    "content": [
                        {"type": "tool_result", "content": json.dumps({"ok": True, "job_id": job_id})}
                    ]
                },
            }
        ),
        json.dumps({"type": "result", "total_cost_usd": 0.012, "usage": {"input_tokens": 10, "output_tokens": 5}}),
    ]

    def runner(cmd: list[str], timeout_s: int) -> Iterator[str]:
        yield from lines

    return runner


class _Say:
    """Assistant say — 첫 호출은 placeholder(채널/ts 반환), 이후 게시물을 기록."""

    def __init__(self) -> None:
        self.posts: list[dict[str, Any]] = []
        self._n = 0

    def __call__(self, text: Any = None, blocks: Any = None) -> dict[str, str]:
        self._n += 1
        self.posts.append({"text": text, "blocks": blocks})
        return {"channel": "C1", "ts": f"100.{self._n}"}


class _Client:
    def __init__(self) -> None:
        self.updates: list[dict[str, Any]] = []
        self.api_calls: list[tuple[str, dict[str, Any]]] = []

    def chat_update(self, **kwargs: Any) -> None:
        self.updates.append(kwargs)

    def api_call(self, method: str, *, json: dict[str, Any]) -> dict[str, Any]:
        self.api_calls.append((method, json))
        return {"ok": True, "canvas_id": "F1"}


def _no_status(_msg: str) -> None:
    return None


def test_flow_diagnose_done_posts_result_and_canvas() -> None:
    store = SqliteJobStore()
    job = store.enqueue("diagnose", "checkout-service", source=JobSource.AGENT, requested_by="agent")
    # worker 시뮬레이트: claim → 완료(L0, 게이트 없음).
    store.claim()
    store.complete(job.id, status=JobStatus.DONE, result="p99 breached 1200ms")

    say, client = _Say(), _Client()
    run_user_message(
        "checkout-service is slow",
        say=say, set_status=_no_status, client=client,
        runner=_propose_stream("diagnose", "checkout-service", job.id),
        mcp_config="", jobs=store, canvas_channel="C9",
        sleep=lambda _s: None,
    )

    # placeholder → 스트리밍 최종 chat_update(footer 포함) 발생.
    assert client.updates and "$0.0120" in client.updates[-1]["text"]
    # 후속: 진단 결과가 스레드에 게시.
    texts = [p["text"] for p in say.posts]
    assert any(t and "p99 breached 1200ms" in t for t in texts)
    # Canvas 생성 호출 + 링크 안내.
    assert client.api_calls and client.api_calls[0][0] == "canvases.create"
    assert any(t and "postmortem canvas" in t for t in texts)


def test_flow_pr_awaiting_posts_approval_buttons_then_click_transitions() -> None:
    store = SqliteJobStore()
    audit = SqliteAuditStore()
    job = store.enqueue("pr", "bump memory", source=JobSource.AGENT, requested_by="agent")
    # worker 시뮬레이트: claim → diff 와 함께 출력 게이트(AWAITING_APPROVAL).
    store.claim()
    store.await_approval(job.id, "diff --git a/x b/x")

    say, client = _Say(), _Client()
    run_user_message(
        "open a PR to bump memory",
        say=say, set_status=_no_status, client=client,
        runner=_propose_stream("pr", "bump memory", job.id),
        mcp_config="", jobs=store, canvas_channel="C9",
        sleep=lambda _s: None,
    )

    # 후속으로 승인 버튼 블록이 스레드에 게시(Canvas 는 pr 이라 미생성).
    blocks_posts = [p for p in say.posts if p["blocks"] is not None]
    assert blocks_posts, "approval buttons should be posted for an awaiting job"
    action_ids = {
        e["action_id"]
        for b in blocks_posts[0]["blocks"]
        if b["type"] == "actions"
        for e in b["elements"]
    }
    assert ACTION_APPROVE in action_ids
    assert not client.api_calls  # pr → Canvas 미생성

    # 버튼 클릭(register_approval_actions 핸들러) → store 전이.
    app = _FakeApp()
    register_approval_actions(app, jobs=store, audit=audit)
    btn_client = _Client()
    app.handlers[ACTION_APPROVE](
        ack=lambda: None,
        body={
            "actions": [{"value": job.id}],
            "user": {"id": "U42"},
            "container": {"message_ts": "100.2"},
            "channel": {"id": "C1"},
        },
        client=btn_client,
    )
    assert store.get(job.id).status is JobStatus.APPROVED  # type: ignore[union-attr]
    assert btn_client.updates and "approved" in btn_client.updates[0]["text"]


class _FakeApp:
    def __init__(self) -> None:
        self.handlers: dict[str, Any] = {}

    def action(self, action_id: str) -> Any:
        def _register(fn: Any) -> Any:
            self.handlers[action_id] = fn
            return fn

        return _register


def test_real_slack_bolt_assistant_constructs_and_wires() -> None:
    """실 slack_bolt 설치 환경: Assistant 생성 + 실 App 장착/액션 등록 호환 스모크.

    slack_bolt 미설치 환경(CI 기본)은 skip — Bolt API(데코레이터/app.use/app.action) 변경 회귀 가드.
    """
    import pytest

    pytest.importorskip("slack_bolt")
    from slack_bolt import App

    from app.approval_actions import register_approval_actions
    from app.assistant_handler import attach_assistant, build_assistant

    assistant = build_assistant(jobs=SqliteJobStore(), canvas_channel="C9", mcp_config="")
    assert type(assistant).__name__ == "Assistant"

    app = App(token="xoxb-x", signing_secret="s", token_verification_enabled=False)
    attach_assistant(app, jobs=SqliteJobStore(), canvas_channel="C9", mcp_config="")
    register_approval_actions(app, jobs=SqliteJobStore())
