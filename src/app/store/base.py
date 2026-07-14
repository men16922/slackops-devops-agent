"""Job store 도메인 모델 + 프로토콜 (이중 컨트롤플레인 공유 큐).

Slack/Web 두 producer 가 같은 큐에 job 을 넣고, 단일 EC2 worker 가 consume 한다.
구현은 주입 가능(JobStore 프로토콜) — 로컬/테스트는 SqliteJobStore, 운영은 DynamoDbJobStore.
clock/id_factory 를 주입해 테스트에서 결정적 순서·식별자를 만든다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol


class JobStatus(str, Enum):
    """job 상태머신.

    PENDING → (L1 쓰기면) AWAITING_APPROVAL → APPROVED → RUNNING → DONE | FAILED.
    읽기(L0) job 은 PENDING → RUNNING → DONE | FAILED. 승인 거부는 REJECTED(종료).
    """

    PENDING = "pending"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    REJECTED = "rejected"


# worker 가 claim 가능한 상태: APPROVED(승인된 쓰기 이어가기) 우선, 그다음 PENDING(신규).
CLAIMABLE_STATUSES: tuple[JobStatus, ...] = (JobStatus.APPROVED, JobStatus.PENDING)

# 종료 상태(더 이상 전이 없음).
TERMINAL_STATUSES: frozenset[JobStatus] = frozenset(
    {JobStatus.DONE, JobStatus.FAILED, JobStatus.REJECTED}
)


class JobSource(str, Enum):
    """job 제출 경로(컨트롤 플레인)."""

    SLACK = "slack"
    WEB = "web"
    AGENT = "agent"  # 운영 에이전트가 MCP propose_job 로 자율 제안(사람 승인 대기)


@dataclass
class Job:
    """큐 job 1건 — 두 인터페이스가 공유하는 상태의 단일 표현.

    Attributes:
        id: 식별자.
        command: subcommand(ping/logs/diagnose/tf-review/pr).
        args: 검증 전 인자 문자열(worker 가 검증·실행).
        source: 제출 경로(slack|web).
        status: 상태머신 현재값.
        requested_by: 요청자(Slack user / web user).
        channel: Slack 채널(웹은 None) — 완료 시 후속 알림용.
        created_at / updated_at: ISO8601 UTC 정렬 가능 문자열.
        diff: L1 쓰기의 승인 대기 diff(출력 게이트).
        result: 실행 결과 텍스트.
        cost_usd / tokens: 계측 메타.
        error: 실패 사유.
        approved_by / approved_at: 승인 메타.
        trace_id: OTel 연계용.
        rationale: source=agent 제안의 근거(에이전트가 왜 이 작업을 올렸는지) — 대시보드 표시용.
    """

    id: str
    command: str
    args: str
    source: JobSource
    status: JobStatus
    requested_by: str
    created_at: str
    updated_at: str
    channel: str | None = None
    diff: str | None = None
    result: str | None = None
    cost_usd: float | None = None
    tokens: int | None = None
    error: str | None = None
    approved_by: str | None = None
    approved_at: str | None = None
    trace_id: str | None = None
    rationale: str | None = None
    execution_plan: str | None = None
    execution_plan_hash: str | None = None
    approval_hash: str | None = None
    extra: dict[str, object] = field(default_factory=dict)


class JobStore(Protocol):
    """이중 컨트롤플레인 공유 job 큐 인터페이스.

    구현은 claim 의 원자성(동시 worker 가 같은 job 을 중복 실행하지 않음)을 보장해야 한다.
    """

    def enqueue(
        self,
        command: str,
        args: str = "",
        *,
        source: JobSource = JobSource.WEB,
        requested_by: str = "",
        channel: str | None = None,
        rationale: str | None = None,
    ) -> Job:
        """새 job 을 PENDING 으로 추가."""
        ...

    def get(self, job_id: str) -> Job | None:
        """id 로 job 조회(없으면 None)."""
        ...

    def list_recent(self, limit: int = 50) -> list[Job]:
        """최신순 job 피드(대시보드용)."""
        ...

    def claim(self) -> Job | None:
        """claim 가능한 가장 오래된 job 을 원자적으로 RUNNING 으로 전이 후 반환(없으면 None)."""
        ...

    def await_approval(
        self,
        job_id: str,
        diff: str,
        *,
        execution_plan: str | None = None,
        execution_plan_hash: str | None = None,
    ) -> Job | None:
        """RUNNING job 을 hash-addressed plan/diff 와 함께 승인 대기로 전이."""
        ...

    def approve(self, job_id: str, approver: str) -> Job | None:
        """AWAITING_APPROVAL → APPROVED(승인자 기록). 상태 불일치면 None."""
        ...

    def reject(self, job_id: str, approver: str) -> Job | None:
        """AWAITING_APPROVAL → REJECTED. 상태 불일치면 None."""
        ...

    def complete(
        self,
        job_id: str,
        *,
        status: JobStatus,
        result: str | None = None,
        cost_usd: float | None = None,
        tokens: int | None = None,
        error: str | None = None,
    ) -> Job | None:
        """RUNNING job 을 종료 상태(DONE|FAILED)로 + 결과/계측 기록."""
        ...
