"""MCP 서버 — Job Queue 를 운영 에이전트(Claude Code Headless)에 노출.

운영 에이전트가 시스템을 관찰(L0)하다 조치가 필요하다고 판단하면, 이 서버의 `propose_job`
도구를 호출해 작업을 큐에 **제안**(source=agent, PENDING)으로 올린다. 실제 실행은 기존 worker
가 담당하고, L1 쓰기(pr 등)는 기존 출력 게이트(await_approval)에서 사람 승인을 기다린다.

설계 불변(주입 방어): 에이전트도 자유 텍스트를 실행 명령으로 직결하지 못한다. propose_job 은
permissions 레지스트리에 대한 **default-deny** — 알려진·허용 레벨 명령만 큐에 들어간다.

구조:
  - `propose_job_impl`/`list_pending_impl`: 순수 로직(JobStore 주입) — MCP SDK 불필요, 테스트 대상.
  - `build_server`: FastMCP 래퍼(lazy import) — 위 순수 로직을 stdio 도구로 노출.
  - `store_from_env`/`main`: `python -m app.mcp_server` stdio 진입점(DDB_ENDPOINT 로 로컬/실 전환).

server name = "slackops" ⇒ 도구 식별자 = `mcp__slackops__propose_job`.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

from app import permissions
from app.store.base import JobSource, JobStatus

if TYPE_CHECKING:  # 타입 체크 전용 — 런타임 import 회피(선택 의존성).
    from app.store.base import JobStore

# 에이전트 제안이 "대기 중"으로 간주되는 상태(중복 제안 회피용 list_pending 필터).
_PENDING_STATUSES: frozenset[str] = frozenset(
    {JobStatus.PENDING.value, JobStatus.AWAITING_APPROVAL.value}
)


def propose_job_impl(
    store: JobStore,
    command: str,
    args: str = "",
    rationale: str = "",
) -> dict[str, object]:
    """에이전트 제안을 큐에 적재(default-deny 검증 후 PENDING/source=agent).

    Args:
        store: 주입된 JobStore.
        command: subcommand(ping/logs/diagnose/tf-review/pr).
        args: 명령 인자(검증 전 — worker 가 검증·실행).
        rationale: 제안 근거(왜 이 작업을 올렸는지) — 대시보드 표시용.

    Returns:
        성공: {"ok": True, "job_id", "status", "command"}.
        거부: {"ok": False, "error"} — 미지/비허용 명령(주입 방어 default deny).
    """
    name = command.strip()
    if not permissions.is_allowed(name):
        return {
            "ok": False,
            "error": (
                f"command not allowed (default deny): {name!r}. "
                f"allowed: {sorted(permissions.known_commands())}"
            ),
        }
    job = store.enqueue(
        name,
        args.strip(),
        source=JobSource.AGENT,
        requested_by="agent",
        rationale=rationale.strip() or None,
    )
    return {
        "ok": True,
        "job_id": job.id,
        "status": job.status.value,
        "command": job.command,
    }


def list_pending_impl(store: JobStore, limit: int = 50) -> list[dict[str, object]]:
    """승인/실행 대기 중인 작업 요약 — 에이전트가 중복 제안을 피하도록.

    PENDING/AWAITING_APPROVAL 만 반환(최신순).
    """
    out: list[dict[str, object]] = []
    for job in store.list_recent(limit):
        if job.status.value in _PENDING_STATUSES:
            out.append(
                {
                    "job_id": job.id,
                    "command": job.command,
                    "args": job.args,
                    "status": job.status.value,
                    "source": job.source.value,
                }
            )
    return out


def store_from_env() -> JobStore:
    """환경에서 JobStore 구성 — DDB_ENDPOINT 있으면 DynamoDB Local, 없으면 실 DynamoDB.

    대시보드가 읽는 같은 단일테이블(`slackops-agent`)에 적재해 제안이 라이브로 노출된다.
    boto3 는 lazy import(미설치 환경 import-safe).
    """
    import boto3  # lazy: 선택 의존성

    table = os.environ.get("DDB_TABLE", "slackops-agent")
    endpoint = os.environ.get("DDB_ENDPOINT")
    region = os.environ.get("AWS_REGION", "us-east-1")
    kwargs: dict[str, Any] = {"region_name": region}
    if endpoint:
        kwargs["endpoint_url"] = endpoint
    dynamodb = boto3.resource("dynamodb", **kwargs)

    from app.store.dynamodb_store import DynamoDbJobStore

    return DynamoDbJobStore(table, dynamodb=dynamodb)


def build_server(store: JobStore) -> Any:
    """FastMCP 서버 구성(lazy import) — 순수 로직을 stdio 도구로 노출.

    server name "slackops" ⇒ 도구 = mcp__slackops__propose_job / mcp__slackops__list_pending.
    """
    from mcp.server.fastmcp import FastMCP  # lazy: 선택 의존성(mcp SDK)

    mcp = FastMCP("slackops")

    @mcp.tool()
    def propose_job(command: str, args: str = "", rationale: str = "") -> dict[str, object]:
        """Propose an operational job to the queue (awaiting human approval). Never execute directly.

        command must be one of: ping/logs/diagnose/tf-review/pr (others are rejected).
        In rationale, write a concise English reason for proposing this job.
        """
        return propose_job_impl(store, command, args, rationale)

    @mcp.tool()
    def list_pending() -> list[dict[str, object]]:
        """승인/실행 대기 중인 작업 목록(중복 제안 회피용)."""
        return list_pending_impl(store)

    return mcp


def main() -> None:
    """stdio MCP 서버 진입점 — `python -m app.mcp_server`."""
    build_server(store_from_env()).run()


if __name__ == "__main__":
    main()
