"""Assistant 콘솔 드라이버 — 실 Slack 없이 Assistant 경로를 터미널에서 재현(D3 로컬 mock 폴백).

`run_user_message` 를 콘솔 fake(say/client)로 구동한다 — Slack 바인딩 표면만 바꾼 것이고
스트리밍/제안/정착 폴링/승인 게이트/Canvas 흐름은 실 코드 그대로다. 발표 현장에서
네트워크/워크스페이스 사고가 나도 같은 시연을 재현하는 백업 경로. 두 모드:

- **기본(real)**: 실 Claude 스트리밍 + propose_job MCP + (별도 기동된) worker 가 정착.
  `make demo` 스택(DynamoDB Local 8931 + web 8930) 위에서 `make demo-assistant`.
- **--mock**: 네트워크/Claude/docker 전부 없이 — canned stream-json replay + in-memory
  SqliteJobStore + worker 시뮬레이트. 승인은 콘솔 [a]/[r] 입력으로
  `approval_actions.apply_decision` 호출(Slack 버튼/web 대시보드와 동일 상태머신).

Canvas 는 콘솔에선 파일로 mock — postmortem markdown 을 로컬 .md 파일로 쓰고 경로를 안내.

설계(assistant_handler 와 동일 철학): 순수 코어(ConsoleSay/ConsoleClient/run_console_turn —
writer·reader 주입, 단위 테스트 가능) + 얇은 CLI(main). 터미널 출력이 이 모듈의 제품
표면이므로 로깅이 아닌 주입된 writer(기본 stdout)로 렌더한다.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from collections.abc import Iterator
from typing import Any, Callable

from app.approval_actions import apply_decision
from app.assistant_handler import (
    GATE_POLL_TIMEOUT_S,
    followup_for,
    poll_job,
    run_user_message,
)
from app.claude_runner import StreamRunner
from app.store.audit_store import AuditStore
from app.store.base import JobSource, JobStatus, JobStore

Writer = Callable[[str], None]
Reader = Callable[[str], str]

CONSOLE_USER = "console-user"
# run_user_message 의 Canvas 경로를 켜기 위한 라벨 — 콘솔에선 채널이 아니라 표기일 뿐.
CONSOLE_CANVAS_CHANNEL = "console"
# mock 스트림 청크 사이 지연(초) — 라이브 스트리밍처럼 보이게 하는 연출값.
MOCK_CHUNK_DELAY_S = 0.25

BANNER = """\
── SlackOps Assistant (console) ─────────────────────────────
Same flow as the Slack Assistant thread, rendered in your
terminal: streaming diagnosis → propose_job → approval gate →
result → postmortem canvas (saved as a local .md file).
Type a request (e.g. "checkout-service is slow"), or "exit".
─────────────────────────────────────────────────────────────
"""

# ── mock 시나리오(canned) — 오프라인 폴백에서 재생할 각본 ────────────────────────
MOCK_SERVICE = "checkout-service"
MOCK_DIAGNOSE_CHUNKS: list[str] = [
    "Looking into *checkout-service*…\n\n",
    "*Signals*\n• p99 latency breached **1240ms** (threshold 800ms)\n"
    "• 5xx ratio spiking on `/api/checkout`\n• Started ~14:05 UTC, after deploy `a1b2c3d`\n",
    "\nThis warrants a full read-only diagnosis (CloudWatch + kubectl + recent diff) — "
    "proposing a `diagnose` job for your approval.",
]
MOCK_DIAGNOSE_RESULT = """\
*Diagnosis — checkout-service*

*Root cause (likely)*: connection-pool exhaustion after deploy `a1b2c3d` halved
`DB_POOL_SIZE` (10 → 5); requests queue on the pool and p99 breaches 1240ms.

*Evidence*
• CloudWatch `checkout-service-prod`: `TimeoutError: connection pool exhausted` × 214 in 15m
• kubectl: pods Ready, no restarts — not a crash loop
• git diff `a1b2c3d`: `config/db.yaml` pool_size 10 → 5

*Suggested next step*: revert the pool_size change (PR), then watch p99 recover.
"""
MOCK_PR_ARGS = "bump memory limit on the api deployment"
MOCK_PR_CHUNKS: list[str] = [
    "Preparing a change for *the api deployment*…\n\n",
    "I'll draft the manifest edit on a branch, run the unit tests, and open a PR — "
    "nothing merges without your approval.\n",
    "\nProposing a `pr` job; the diff will be posted here for review.",
]
MOCK_PR_DIFF = """\
diff --git a/k8s/api-deployment.yaml b/k8s/api-deployment.yaml
--- a/k8s/api-deployment.yaml
+++ b/k8s/api-deployment.yaml
@@ -21,7 +21,7 @@ spec:
         resources:
           limits:
-            memory: "512Mi"
+            memory: "1Gi"
             cpu: "500m"
"""
MOCK_PR_RESULT = (
    ":white_check_mark: PR opened: https://github.com/example/infra/pull/42 "
    "(branch `slackops/bump-api-memory`, unit tests green). Merge is still human-gated."
)


def _mock_lines(command: str, args: str, job_id: str, chunks: list[str]) -> list[str]:
    """canned 청크를 claude stream-json 이벤트 라인으로 조립(테스트 픽스처와 동일 형식)."""
    lines = [
        json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": c}]}})
        for c in chunks
    ]
    lines.append(
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
        )
    )
    lines.append(
        json.dumps(
            {
                "type": "user",
                "message": {
                    "content": [
                        {"type": "tool_result", "content": json.dumps({"ok": True, "job_id": job_id})}
                    ]
                },
            }
        )
    )
    lines.append(
        json.dumps(
            {
                "type": "result",
                "total_cost_usd": 0.0,
                "usage": {"input_tokens": 812, "output_tokens": 236},
            }
        )
    )
    return lines


def mock_stream_runner(
    lines: list[str],
    *,
    sleep: Callable[[float], None] = time.sleep,
    delay_s: float = MOCK_CHUNK_DELAY_S,
) -> StreamRunner:
    """녹화된 stream-json 라인을 지연을 두고 재생하는 StreamRunner(오프라인 폴백)."""

    def _runner(cmd: list[str], timeout_s: int) -> Iterator[str]:
        for line in lines:
            sleep(delay_s)
            yield line

    return _runner


def _looks_like_pr(text: str) -> bool:
    lowered = text.lower()
    return "pr" in lowered.split() or "pull request" in lowered or "open a pr" in lowered


def build_mock_turn(
    jobs: JobStore,
    text: str,
    *,
    sleep: Callable[[float], None] = time.sleep,
    delay_s: float = MOCK_CHUNK_DELAY_S,
) -> StreamRunner:
    """mock 턴 준비 — job 을 store 에 적재해 미리 정착시키고 replay runner 를 돌려준다.

    diagnose 시나리오는 DONE(결과+Canvas), pr 시나리오는 AWAITING_APPROVAL(diff+승인 게이트)
    까지 worker 를 시뮬레이트한다(통합테스트 test_assistant_flow 와 동일 기법).
    """
    if _looks_like_pr(text):
        job = jobs.enqueue("pr", MOCK_PR_ARGS, source=JobSource.AGENT, requested_by=CONSOLE_USER)
        jobs.claim()
        jobs.await_approval(job.id, MOCK_PR_DIFF)
        command, args, chunks = "pr", MOCK_PR_ARGS, MOCK_PR_CHUNKS
    else:
        job = jobs.enqueue(
            "diagnose", MOCK_SERVICE, source=JobSource.AGENT, requested_by=CONSOLE_USER
        )
        jobs.claim()
        jobs.complete(job.id, status=JobStatus.DONE, result=MOCK_DIAGNOSE_RESULT)
        command, args, chunks = "diagnose", MOCK_SERVICE, MOCK_DIAGNOSE_CHUNKS
    return mock_stream_runner(_mock_lines(command, args, job.id, chunks), sleep=sleep, delay_s=delay_s)


def simulate_worker_execute(jobs: JobStore, job_id: str) -> None:
    """mock 모드에서 승인 이후의 worker execute 를 시뮬레이트(APPROVED→RUNNING→DONE).

    mock store 는 이 콘솔 전용 in-memory 라 claim 경쟁이 없다 — 그래도 다른 job 을
    잡았으면 건드리지 않고 반환(방어적).
    """
    claimed = jobs.claim()
    if claimed is None or claimed.id != job_id:
        return
    jobs.complete(job_id, status=JobStatus.DONE, result=MOCK_PR_RESULT)


# ── 콘솔 fake Slack 표면 ─────────────────────────────────────────────────────
def render_blocks(blocks: list[dict[str, Any]]) -> str:
    """Block Kit 블록을 콘솔 텍스트로 렌더(section 본문 + 버튼 라벨)."""
    parts: list[str] = []
    for block in blocks:
        if block.get("type") == "section":
            parts.append(str((block.get("text") or {}).get("text", "")))
        elif block.get("type") == "actions":
            labels = " / ".join(
                str((e.get("text") or {}).get("text", "")) for e in block.get("elements", [])
            )
            parts.append(f"[buttons] {labels}")
    return "\n".join(p for p in parts if p)


class ConsoleSay:
    """Assistant say fake — placeholder(첫 호출)는 스트리밍 렌더가 대체하므로 출력 생략."""

    def __init__(self, write: Writer) -> None:
        self.posts: list[dict[str, Any]] = []
        self._write = write
        self._n = 0

    def __call__(self, text: Any = None, blocks: Any = None) -> dict[str, str]:
        self._n += 1
        self.posts.append({"text": text, "blocks": blocks})
        if self._n > 1:
            rendered = str(text or "")
            if blocks:
                rendered = (rendered + "\n" if rendered else "") + render_blocks(blocks)
            self._write("\n\n" + rendered + "\n")
        return {"channel": "console", "ts": f"console.{self._n}"}


class ConsoleClient:
    """Slack WebClient fake — chat.update 는 증분 스트리밍 렌더, canvases.create 는 파일 mock."""

    def __init__(self, write: Writer, *, canvas_dir: str | None = None) -> None:
        self._write = write
        self._prev = ""
        self._canvas_dir = canvas_dir
        self.canvas_paths: list[str] = []

    def chat_update(self, *, channel: str, ts: str, text: str, blocks: Any = None) -> None:
        # 누적 텍스트의 접두 증분만 출력 → 터미널에서 타이핑되듯 렌더.
        if text.startswith(self._prev):
            self._write(text[len(self._prev) :])
        else:
            self._write("\n" + text)
        self._prev = text

    def api_call(self, method: str, *, json: dict[str, Any]) -> dict[str, Any]:
        if method != "canvases.create":
            return {"ok": False, "error": f"console client does not mock {method}"}
        markdown = str((json.get("document_content") or {}).get("markdown", ""))
        title = str(json.get("title", "postmortem"))
        fd, path = tempfile.mkstemp(
            prefix="slackops-postmortem-", suffix=".md", dir=self._canvas_dir
        )
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(markdown)
        self.canvas_paths.append(path)
        self._write(f"\n:memo: (mock canvas) “{title}” → {path}\n")
        return {"ok": True, "canvas_id": path}


def pending_decision(posts: list[dict[str, Any]]) -> str | None:
    """say 게시물에서 승인 버튼 블록(block_id=approval:<job_id>)의 대상 job 을 찾는다."""
    for post in reversed(posts):
        for block in post.get("blocks") or []:
            block_id = str(block.get("block_id", ""))
            if block.get("type") == "actions" and block_id.startswith("approval:"):
                return block_id.split(":", 1)[1]
    return None


def run_console_turn(
    text: str,
    *,
    jobs: JobStore,
    audit: AuditStore | None = None,
    write: Writer,
    read_input: Reader,
    mock: bool = False,
    runner: StreamRunner | None = None,
    canvas_channel: str = CONSOLE_CANVAS_CHANNEL,
    canvas_dir: str | None = None,
    sleep: Callable[[float], None] = time.sleep,
    delay_s: float = MOCK_CHUNK_DELAY_S,
    poll_timeout_s: float = GATE_POLL_TIMEOUT_S,
) -> None:
    """콘솔 턴 1회 — run_user_message 실행 후, 승인 게이트가 열리면 콘솔에서 결정을 받는다.

    승인([a])은 apply_decision(Slack 버튼과 동일 상태머신) → mock 이면 worker execute 를
    시뮬레이트, real 이면 별도 worker 가 집는다 → 정착을 다시 폴링해 결과를 렌더.
    """
    say = ConsoleSay(write)
    client = ConsoleClient(write, canvas_dir=canvas_dir)
    active_runner = runner
    mcp_config: str | None = None
    if mock and active_runner is None:
        active_runner = build_mock_turn(jobs, text, sleep=sleep, delay_s=delay_s)
        mcp_config = ""  # replay 라 MCP 불필요 — 실 mcp_config_json() 조립을 건너뛴다.

    run_user_message(
        text,
        say=say,
        set_status=lambda _msg: None,
        client=client,
        runner=active_runner,
        mcp_config=mcp_config,
        jobs=jobs,
        canvas_channel=canvas_channel,
        poll_timeout_s=poll_timeout_s,
        sleep=sleep,
        throttle_s=0.0,  # 콘솔은 rate limit 이 없다 — 청크마다 즉시 렌더.
    )
    write("\n")

    job_id = pending_decision(say.posts)
    if job_id is None:
        return
    answer = read_input("gate> [a]pprove / [r]eject / enter=leave queued: ").strip().lower()
    if not answer or answer[0] not in {"a", "r"}:
        write("… left awaiting approval in the queue (dashboard can decide later).\n")
        return
    approve = answer.startswith("a")
    decision = apply_decision(
        jobs, job_id=job_id, approver=CONSOLE_USER, approve=approve, audit=audit
    )
    write(decision.message + "\n")
    if not decision.ok or not approve:
        return

    if mock:
        simulate_worker_execute(jobs, job_id)
    final = poll_job(jobs, job_id, timeout_s=poll_timeout_s, sleep=sleep)
    follow_text, _blocks = followup_for(final)
    write("\n" + follow_text + "\n")


def _stores_from_args(mock: bool) -> tuple[JobStore, AuditStore]:
    """모드에 맞는 store 구성 — mock 은 in-memory(오프라인), real 은 env(DDB_ENDPOINT/실 DDB)."""
    if mock:
        from app.store.audit_store import SqliteAuditStore
        from app.store.sqlite_store import SqliteJobStore

        return SqliteJobStore(), SqliteAuditStore()
    from app.mcp_server import audit_store_from_env, store_from_env

    return store_from_env(), audit_store_from_env()


def main() -> None:
    """CLI — `python -m app.assistant_console [--mock] [--once TEXT]`. 콘솔 Assistant REPL."""
    parser = argparse.ArgumentParser(
        description="SlackOps Assistant 콘솔 드라이버(실 Slack 없이 Assistant 경로 재현)"
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="오프라인 폴백 — canned 스트림 replay + in-memory store(네트워크/Claude 불필요)",
    )
    parser.add_argument("--once", metavar="TEXT", help="한 턴만 처리하고 종료")
    parser.add_argument(
        "--poll-timeout",
        type=float,
        default=GATE_POLL_TIMEOUT_S,
        help="제안 job 정착 폴링 타임아웃(초) — real 모드의 diagnose 는 실 Claude 라 길 수 있다",
    )
    args = parser.parse_args()

    def write(s: str) -> None:
        sys.stdout.write(s)
        sys.stdout.flush()

    jobs, audit = _stores_from_args(args.mock)
    canvas_channel = os.environ.get("SLACK_NOTIFY_CHANNEL", CONSOLE_CANVAS_CHANNEL)

    def turn(text: str) -> None:
        run_console_turn(
            text,
            jobs=jobs,
            audit=audit,
            write=write,
            read_input=input,
            mock=args.mock,
            canvas_channel=canvas_channel,
            poll_timeout_s=args.poll_timeout,
        )

    write(BANNER)
    if args.mock:
        write("(mock mode — offline replay, in-memory store, $0)\n\n")
    if args.once:
        turn(args.once)
        return
    while True:
        try:
            text = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            write("\n")
            return
        if not text:
            continue
        if text.lower() in {"exit", "quit"}:
            return
        turn(text)


if __name__ == "__main__":
    main()
