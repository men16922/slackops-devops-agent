"""SQLite job queue (MVP 한정).

비동기 명령 실행을 위한 단순 작업 큐. **MVP 한정 — prod 데이터스토어로 호칭/사용 금지.**
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class JobStatus(str, Enum):
    """작업 상태."""

    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


@dataclass
class Job:
    """큐 작업 항목.

    Attributes:
        id: 작업 식별자.
        command: 실행할 subcommand 이름.
        payload: 명령 인자(검증된 값).
        status: 현재 상태.
    """

    id: str
    command: str
    payload: dict[str, object]
    status: JobStatus = JobStatus.PENDING


class JobQueue:
    """SQLite 기반 작업 큐 (MVP)."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path

    def enqueue(self, command: str, payload: dict[str, object]) -> Job:
        """작업 추가."""
        raise NotImplementedError("Day 1–3: SQLite enqueue 구현 예정")

    def dequeue(self) -> Job | None:
        """다음 PENDING 작업 반환(없으면 None)."""
        raise NotImplementedError("Day 1–3: SQLite dequeue 구현 예정")

    def update_status(self, job_id: str, status: JobStatus) -> None:
        """작업 상태 갱신."""
        raise NotImplementedError("Day 1–3: SQLite status 갱신 구현 예정")
