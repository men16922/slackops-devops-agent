"""SQLite job queue (MVP 한정).

비동기 명령 실행을 위한 단순 작업 큐. **MVP 한정 — prod 데이터스토어로 호칭/사용 금지.**
stdlib sqlite3 만 사용. 단일 프로세스 내 다중 워커 기준(동시 dequeue 는 트랜잭션으로 원자 클레임).
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from enum import Enum

_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id         TEXT PRIMARY KEY,
    command    TEXT NOT NULL,
    payload    TEXT NOT NULL,
    status     TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status, created_at);
"""


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
        self._conn = sqlite3.connect(db_path, isolation_level=None)
        self._conn.executescript(_SCHEMA)

    def close(self) -> None:
        """DB 연결 종료."""
        self._conn.close()

    def enqueue(self, command: str, payload: dict[str, object]) -> Job:
        """작업 추가(PENDING)."""
        job = Job(id=str(uuid.uuid4()), command=command, payload=payload)
        self._conn.execute(
            "INSERT INTO jobs (id, command, payload, status) VALUES (?, ?, ?, ?)",
            (job.id, job.command, json.dumps(job.payload), job.status.value),
        )
        return job

    def dequeue(self) -> Job | None:
        """가장 오래된 PENDING 작업을 원자적으로 RUNNING 으로 클레임 후 반환(없으면 None)."""
        cur = self._conn.execute(
            """
            UPDATE jobs SET status = ?
            WHERE id = (
                SELECT id FROM jobs WHERE status = ? ORDER BY created_at LIMIT 1
            )
            RETURNING id, command, payload
            """,
            (JobStatus.RUNNING.value, JobStatus.PENDING.value),
        )
        row = cur.fetchone()
        if row is None:
            return None
        job_id, command, payload = row
        return Job(id=job_id, command=command, payload=json.loads(payload), status=JobStatus.RUNNING)

    def update_status(self, job_id: str, status: JobStatus) -> None:
        """작업 상태 갱신.

        Raises:
            KeyError: 존재하지 않는 job_id.
        """
        cur = self._conn.execute(
            "UPDATE jobs SET status = ? WHERE id = ?", (status.value, job_id)
        )
        if cur.rowcount == 0:
            raise KeyError(f"job not found: {job_id!r}")
