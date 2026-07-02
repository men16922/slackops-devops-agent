"""assistant_console(D3 로컬 mock 폴백) — 실 Slack/Claude/네트워크 없이 콘솔 턴 검증.

mock 시나리오(diagnose/pr)가 run_user_message 실 코드 경로(스트리밍→제안→정착→후속→Canvas)
를 그대로 타는지, 승인 게이트가 Slack 버튼과 동일한 apply_decision 상태머신으로 전이하는지
를 콘솔 fake(writer/reader 주입)로 끝까지 돌려 확인한다.
"""

from __future__ import annotations

from typing import Any

from app.assistant_console import (
    MOCK_PR_RESULT,
    ConsoleClient,
    pending_decision,
    run_console_turn,
)
from app.store.audit_store import SqliteAuditStore
from app.store.base import JobStatus
from app.store.sqlite_store import SqliteJobStore


class _Console:
    """writer/reader fake — 출력을 누적하고, 게이트 질문에 canned 답을 준다."""

    def __init__(self, answers: list[str] | None = None) -> None:
        self.out: list[str] = []
        self.prompts: list[str] = []
        self._answers = list(answers or [])

    def write(self, s: str) -> None:
        self.out.append(s)

    def read(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self._answers.pop(0) if self._answers else ""

    @property
    def text(self) -> str:
        return "".join(self.out)


def _turn(store: SqliteJobStore, console: _Console, message: str, tmp_path: Any) -> None:
    run_console_turn(
        message,
        jobs=store,
        audit=SqliteAuditStore(),
        write=console.write,
        read_input=console.read,
        mock=True,
        canvas_dir=str(tmp_path),
        sleep=lambda _s: None,
        delay_s=0.0,
    )


def test_mock_diagnose_streams_result_and_canvas_file(tmp_path: Any) -> None:
    store = SqliteJobStore()
    console = _Console()
    _turn(store, console, "checkout-service is slow", tmp_path)

    # 스트리밍 본문 + footer(토큰/도구호출) 렌더.
    assert "connection pool exhausted" in console.text or "checkout-service" in console.text
    assert "tokens" in console.text
    # 후속으로 진단 결과가 게시되고, mock Canvas 파일이 생성됨.
    assert "Root cause" in console.text
    canvases = list(tmp_path.glob("slackops-postmortem-*.md"))
    assert canvases, "postmortem canvas file should be written"
    assert "Incident Postmortem" in canvases[0].read_text(encoding="utf-8")
    # 진단(DONE)은 승인 게이트가 없다 — 게이트 질문 미발생.
    assert not console.prompts


def test_mock_pr_gate_approve_runs_to_done(tmp_path: Any) -> None:
    store = SqliteJobStore()
    console = _Console(answers=["a"])
    _turn(store, console, "open a PR to bump the memory limit", tmp_path)

    # diff 미리보기 + 버튼 렌더 → 게이트 질문 → 승인 → 시뮬레이트 execute → DONE 결과.
    assert "Approval required" in console.text
    assert "memory:" in console.text  # diff preview
    assert console.prompts, "gate prompt should be asked"
    assert "approved by" in console.text
    assert MOCK_PR_RESULT in console.text
    done = [j for j in _all_jobs(store) if j.command == "pr"]
    assert done and done[0].status is JobStatus.DONE


def test_mock_pr_gate_reject_discards(tmp_path: Any) -> None:
    store = SqliteJobStore()
    console = _Console(answers=["r"])
    _turn(store, console, "open a PR to bump the memory limit", tmp_path)

    assert "rejected by" in console.text
    pr_jobs = [j for j in _all_jobs(store) if j.command == "pr"]
    assert pr_jobs and pr_jobs[0].status is JobStatus.REJECTED


def test_mock_pr_gate_skip_leaves_awaiting(tmp_path: Any) -> None:
    store = SqliteJobStore()
    console = _Console(answers=[""])
    _turn(store, console, "open a PR to bump the memory limit", tmp_path)

    assert "left awaiting approval" in console.text
    pr_jobs = [j for j in _all_jobs(store) if j.command == "pr"]
    assert pr_jobs and pr_jobs[0].status is JobStatus.AWAITING_APPROVAL


def test_console_client_streams_prefix_delta() -> None:
    out: list[str] = []
    client = ConsoleClient(out.append)
    client.chat_update(channel="c", ts="t", text="Hello")
    client.chat_update(channel="c", ts="t", text="Hello world")
    client.chat_update(channel="c", ts="t", text="Fresh text")  # 접두 아님 → 줄바꿈 후 전체
    assert out == ["Hello", " world", "\nFresh text"]


def test_pending_decision_parses_block_id() -> None:
    posts: list[dict[str, Any]] = [
        {"text": "hi", "blocks": None},
        {
            "text": "review",
            "blocks": [{"type": "actions", "block_id": "approval:job-42", "elements": []}],
        },
    ]
    assert pending_decision(posts) == "job-42"
    assert pending_decision([{"text": "hi", "blocks": None}]) is None


def _all_jobs(store: SqliteJobStore) -> list[Any]:
    return [j for j in (store.get(i) for i in _job_ids(store)) if j is not None]


def _job_ids(store: SqliteJobStore) -> list[str]:
    rows = store._conn.execute("SELECT id FROM jobs").fetchall()  # noqa: SLF001 — 테스트 편의
    return [str(r["id"]) for r in rows]
