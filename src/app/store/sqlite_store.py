"""JobStore 의 SQLite 구현 — 로컬/테스트용(운영은 DynamoDbJobStore).

claim 은 BEGIN IMMEDIATE 트랜잭션으로 원자적 — 동시 worker 가 같은 job 을 중복 claim 하지 않는다.
clock/id_factory 주입으로 테스트에서 결정적 순서·식별자를 만든다.
"""

from __future__ import annotations

import sqlite3
import uuid
from collections.abc import Callable

from app.store._util import utcnow_iso as _utcnow_iso
from app.store.base import (
    CLAIMABLE_STATUSES,
    ORPHANED_RUNNING_ERROR,
    Job,
    JobSource,
    JobStatus,
)

_COLUMNS = (
    "id, command, args, source, status, requested_by, channel, created_at, updated_at, "
    "diff, result, cost_usd, tokens, error, approved_by, approved_at, trace_id, rationale, "
    "execution_plan, execution_plan_hash, approval_hash"
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id           TEXT PRIMARY KEY,
    command      TEXT NOT NULL,
    args         TEXT NOT NULL DEFAULT '',
    source       TEXT NOT NULL,
    status       TEXT NOT NULL,
    requested_by TEXT NOT NULL DEFAULT '',
    channel      TEXT,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL,
    diff         TEXT,
    result       TEXT,
    cost_usd     REAL,
    tokens       INTEGER,
    error        TEXT,
    approved_by  TEXT,
    approved_at  TEXT,
    trace_id     TEXT,
    rationale    TEXT,
    execution_plan TEXT,
    execution_plan_hash TEXT,
    approval_hash TEXT
);
CREATE INDEX IF NOT EXISTS idx_jobs_status_created ON jobs(status, created_at);
"""


class SqliteJobStore:
    """SQLite 기반 JobStore 구현."""

    def __init__(
        self,
        db_path: str = ":memory:",
        *,
        clock: Callable[[], str] | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._clock = clock or _utcnow_iso
        self._id_factory = id_factory or (lambda: str(uuid.uuid4()))
        self._conn = sqlite3.connect(db_path, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)

    def close(self) -> None:
        self._conn.close()

    # ── producer ──────────────────────────────────────────────
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
        now = self._clock()
        job = Job(
            id=self._id_factory(),
            command=command,
            args=args,
            source=source,
            status=JobStatus.PENDING,
            requested_by=requested_by,
            channel=channel,
            created_at=now,
            updated_at=now,
            rationale=rationale,
        )
        self._conn.execute(
            f"INSERT INTO jobs ({_COLUMNS}) VALUES "
            "(:id, :command, :args, :source, :status, :requested_by, :channel, "
            ":created_at, :updated_at, :diff, :result, :cost_usd, :tokens, :error, "
            ":approved_by, :approved_at, :trace_id, :rationale, :execution_plan, "
            ":execution_plan_hash, :approval_hash)",
            _to_row(job),
        )
        return job

    # ── readers ───────────────────────────────────────────────
    def get(self, job_id: str) -> Job | None:
        row = self._conn.execute(
            f"SELECT {_COLUMNS} FROM jobs WHERE id = ?", (job_id,)
        ).fetchone()
        return _from_row(row) if row else None

    def list_recent(self, limit: int = 50) -> list[Job]:
        rows = self._conn.execute(
            f"SELECT {_COLUMNS} FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [_from_row(row) for row in rows]

    # ── consumer (worker) ─────────────────────────────────────
    def claim(self) -> Job | None:
        """APPROVED 우선, 그다음 PENDING 중 가장 오래된 1건을 원자적으로 RUNNING 으로."""
        order = ", ".join(f"'{s.value}'" for s in CLAIMABLE_STATUSES)
        priority = " ".join(
            f"WHEN '{s.value}' THEN {i}" for i, s in enumerate(CLAIMABLE_STATUSES)
        )
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            row = self._conn.execute(
                f"SELECT id, status FROM jobs WHERE status IN ({order}) "
                f"ORDER BY CASE status {priority} END, created_at LIMIT 1"
            ).fetchone()
            if row is None:
                self._conn.execute("COMMIT")
                return None
            now = self._clock()
            self._conn.execute(
                "UPDATE jobs SET status = ?, updated_at = ? WHERE id = ? AND status = ?",
                (JobStatus.RUNNING.value, now, row["id"], row["status"]),
            )
            self._conn.execute("COMMIT")
        except Exception:
            self._conn.execute("ROLLBACK")
            raise
        return self.get(row["id"])

    def reclaim_stale_running(self, older_than: str) -> list[Job]:
        """updated_at < older_than 인 RUNNING job 을 FAILED 로 원자 전이(고아 회수)."""
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            rows = self._conn.execute(
                "SELECT id FROM jobs WHERE status = ? AND updated_at < ?",
                (JobStatus.RUNNING.value, older_than),
            ).fetchall()
            now = self._clock()
            reclaimed_ids: list[str] = []
            for row in rows:
                cur = self._conn.execute(
                    "UPDATE jobs SET status = ?, error = ?, updated_at = ? "
                    "WHERE id = ? AND status = ?",
                    (
                        JobStatus.FAILED.value,
                        ORPHANED_RUNNING_ERROR,
                        now,
                        row["id"],
                        JobStatus.RUNNING.value,
                    ),
                )
                if cur.rowcount:
                    reclaimed_ids.append(row["id"])
            self._conn.execute("COMMIT")
        except Exception:
            self._conn.execute("ROLLBACK")
            raise
        return [job for job_id in reclaimed_ids if (job := self.get(job_id)) is not None]

    # ── 출력 게이트 / 종료 ─────────────────────────────────────
    def await_approval(
        self,
        job_id: str,
        diff: str,
        *,
        execution_plan: str | None = None,
        execution_plan_hash: str | None = None,
    ) -> Job | None:
        return self._transition(
            job_id,
            expected=JobStatus.RUNNING,
            new=JobStatus.AWAITING_APPROVAL,
            extra={
                "diff": diff,
                "execution_plan": execution_plan,
                "execution_plan_hash": execution_plan_hash,
            },
        )

    def approve(self, job_id: str, approver: str) -> Job | None:
        job = self.get(job_id)
        if job is None or not job.execution_plan_hash:
            return None
        return self._transition(
            job_id,
            expected=JobStatus.AWAITING_APPROVAL,
            new=JobStatus.APPROVED,
            extra={
                "approved_by": approver,
                "approved_at": self._clock(),
                "approval_hash": job.execution_plan_hash,
            },
        )

    def reject(self, job_id: str, approver: str) -> Job | None:
        return self._transition(
            job_id,
            expected=JobStatus.AWAITING_APPROVAL,
            new=JobStatus.REJECTED,
            extra={"approved_by": approver, "approved_at": self._clock()},
        )

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
        return self._transition(
            job_id,
            expected=JobStatus.RUNNING,
            new=status,
            extra={
                "result": result,
                "cost_usd": cost_usd,
                "tokens": tokens,
                "error": error,
            },
        )

    # ── 내부 ──────────────────────────────────────────────────
    def _transition(
        self,
        job_id: str,
        *,
        expected: JobStatus,
        new: JobStatus,
        extra: dict[str, object],
    ) -> Job | None:
        """expected 상태일 때만 new 로 전이(조건부) + extra 필드 갱신. 불일치면 None."""
        sets = ["status = :status", "updated_at = :updated_at"]
        params: dict[str, object] = {
            "status": new.value,
            "updated_at": self._clock(),
            "id": job_id,
            "expected": expected.value,
        }
        for key, value in extra.items():
            if value is not None:
                sets.append(f"{key} = :{key}")
                params[key] = value
        cur = self._conn.execute(
            f"UPDATE jobs SET {', '.join(sets)} WHERE id = :id AND status = :expected",
            params,
        )
        if cur.rowcount == 0:
            return None
        return self.get(job_id)


def _to_row(job: Job) -> dict[str, object]:
    return {
        "id": job.id,
        "command": job.command,
        "args": job.args,
        "source": job.source.value,
        "status": job.status.value,
        "requested_by": job.requested_by,
        "channel": job.channel,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
        "diff": job.diff,
        "result": job.result,
        "cost_usd": job.cost_usd,
        "tokens": job.tokens,
        "error": job.error,
        "approved_by": job.approved_by,
        "approved_at": job.approved_at,
        "trace_id": job.trace_id,
        "rationale": job.rationale,
        "execution_plan": job.execution_plan,
        "execution_plan_hash": job.execution_plan_hash,
        "approval_hash": job.approval_hash,
    }


def _from_row(row: sqlite3.Row) -> Job:
    return Job(
        id=row["id"],
        command=row["command"],
        args=row["args"],
        source=JobSource(row["source"]),
        status=JobStatus(row["status"]),
        requested_by=row["requested_by"],
        channel=row["channel"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        diff=row["diff"],
        result=row["result"],
        cost_usd=row["cost_usd"],
        tokens=row["tokens"],
        error=row["error"],
        approved_by=row["approved_by"],
        approved_at=row["approved_at"],
        trace_id=row["trace_id"],
        rationale=row["rationale"],
        execution_plan=row["execution_plan"],
        execution_plan_hash=row["execution_plan_hash"],
        approval_hash=row["approval_hash"],
    )
