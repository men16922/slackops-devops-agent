"""Telemetry store — 실행 1건당 계측 지표 기록 (단일테이블 Metric 항목).

키 설계(docs/plans/2026-06-12-h0-hackathon.md, DECISIONS D5):
  Metric  PK=JOB#{id}  SK=METRIC#{ts}  GSI2=METRIC#{yyyymmdd}/{ts}
job 단위 조회(list_for_job)와 일자별 피드(list_feed — 대시보드)를 모두 지원한다.

구현은 주입 가능(TelemetryStore 프로토콜) — 로컬/테스트 SqliteTelemetryStore,
운영 DynamoDbTelemetryStore. boto3 는 lazy import 로 미설치 환경에서도 import-safe.
같은 (job_id, ts) 재기록은 최신값 덮어쓰기 — DynamoDB put_item 과 SQLite
INSERT OR REPLACE 가 동치 (실 clock 은 μs 해상도라 사실상 충돌 없음).
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from app.store._util import (
    day_of as _day_of,
    encode_for_dynamodb as _encode,
    utcnow_iso as _utcnow_iso,
)


@dataclass
class MetricRecord:
    """실행 1건의 계측 지표 — latency/토큰/비용/tool call/성패.

    Attributes:
        job_id: 대상 job 식별자.
        ts: ISO8601 UTC 정렬 가능 문자열(기록 시각).
        command: 실행된 subcommand(ping/logs/diagnose/...).
        duration_ms: end-to-end 실행 latency.
        tokens: 사용 토큰 수.
        cost_usd: 호출당 비용 USD.
        tool_calls: tool call 횟수.
        success: 성공 여부(실패율 집계용).
        error: 실패 사유.
    """

    job_id: str
    ts: str
    command: str = ""
    duration_ms: float | None = None
    tokens: int | None = None
    cost_usd: float | None = None
    tool_calls: int | None = None
    success: bool = True
    error: str | None = None


class TelemetryStore(Protocol):
    """계측 지표 저장소 인터페이스."""

    def record(
        self,
        job_id: str,
        *,
        command: str = "",
        duration_ms: float | None = None,
        tokens: int | None = None,
        cost_usd: float | None = None,
        tool_calls: int | None = None,
        success: bool = True,
        error: str | None = None,
    ) -> MetricRecord:
        """실행 1건의 지표를 기록."""
        ...

    def list_for_job(self, job_id: str, limit: int = 100) -> list[MetricRecord]:
        """job 1건의 지표를 시간순(오래된 것부터)으로."""
        ...

    def list_feed(self, day: str | None = None, limit: int = 50) -> list[MetricRecord]:
        """일자(yyyymmdd, 기본=현재 clock 일자) 피드를 최신순으로(대시보드용)."""
        ...


# ── SQLite 구현 (로컬/테스트) ─────────────────────────────────

_SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS metrics (
    job_id      TEXT NOT NULL,
    ts          TEXT NOT NULL,
    day         TEXT NOT NULL,
    command     TEXT NOT NULL DEFAULT '',
    duration_ms REAL,
    tokens      INTEGER,
    cost_usd    REAL,
    tool_calls  INTEGER,
    success     INTEGER NOT NULL DEFAULT 1,
    error       TEXT,
    PRIMARY KEY (job_id, ts)
);
CREATE INDEX IF NOT EXISTS idx_metrics_day_ts ON metrics(day, ts);
"""

_SQLITE_COLUMNS = "job_id, ts, command, duration_ms, tokens, cost_usd, tool_calls, success, error"


class SqliteTelemetryStore:
    """SQLite 기반 TelemetryStore 구현."""

    def __init__(
        self,
        db_path: str = ":memory:",
        *,
        clock: Callable[[], str] | None = None,
    ) -> None:
        self._clock = clock or _utcnow_iso
        self._conn = sqlite3.connect(db_path, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SQLITE_SCHEMA)

    def close(self) -> None:
        self._conn.close()

    def record(
        self,
        job_id: str,
        *,
        command: str = "",
        duration_ms: float | None = None,
        tokens: int | None = None,
        cost_usd: float | None = None,
        tool_calls: int | None = None,
        success: bool = True,
        error: str | None = None,
    ) -> MetricRecord:
        metric = MetricRecord(
            job_id=job_id,
            ts=self._clock(),
            command=command,
            duration_ms=duration_ms,
            tokens=tokens,
            cost_usd=cost_usd,
            tool_calls=tool_calls,
            success=success,
            error=error,
        )
        self._conn.execute(
            f"INSERT OR REPLACE INTO metrics ({_SQLITE_COLUMNS}, day) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                metric.job_id,
                metric.ts,
                metric.command,
                metric.duration_ms,
                metric.tokens,
                metric.cost_usd,
                metric.tool_calls,
                int(metric.success),
                metric.error,
                _day_of(metric.ts),
            ),
        )
        return metric

    def list_for_job(self, job_id: str, limit: int = 100) -> list[MetricRecord]:
        rows = self._conn.execute(
            f"SELECT {_SQLITE_COLUMNS} FROM metrics WHERE job_id = ? ORDER BY ts LIMIT ?",
            (job_id, limit),
        ).fetchall()
        return [_from_sqlite_row(row) for row in rows]

    def list_feed(self, day: str | None = None, limit: int = 50) -> list[MetricRecord]:
        day = day or _day_of(self._clock())
        rows = self._conn.execute(
            f"SELECT {_SQLITE_COLUMNS} FROM metrics WHERE day = ? ORDER BY ts DESC LIMIT ?",
            (day, limit),
        ).fetchall()
        return [_from_sqlite_row(row) for row in rows]


def _from_sqlite_row(row: sqlite3.Row) -> MetricRecord:
    return MetricRecord(
        job_id=row["job_id"],
        ts=row["ts"],
        command=row["command"],
        duration_ms=row["duration_ms"],
        tokens=row["tokens"],
        cost_usd=row["cost_usd"],
        tool_calls=row["tool_calls"],
        success=bool(row["success"]),
        error=row["error"],
    )


# ── DynamoDB 구현 (운영 — JobStore 와 같은 단일테이블) ─────────


class DynamoDbTelemetryStore:
    """DynamoDB 단일테이블 TelemetryStore 구현 (Job META 항목과 같은 테이블 공존)."""

    def __init__(
        self,
        table_name: str = "slackops-agent",
        *,
        dynamodb: Any | None = None,
        clock: Callable[[], str] | None = None,
    ) -> None:
        self._clock = clock or _utcnow_iso
        if dynamodb is None:
            import boto3  # lazy: 미설치/자격증명 없는 환경 import-safe

            dynamodb = boto3.resource("dynamodb")
        self._table = dynamodb.Table(table_name)

    def record(
        self,
        job_id: str,
        *,
        command: str = "",
        duration_ms: float | None = None,
        tokens: int | None = None,
        cost_usd: float | None = None,
        tool_calls: int | None = None,
        success: bool = True,
        error: str | None = None,
    ) -> MetricRecord:
        metric = MetricRecord(
            job_id=job_id,
            ts=self._clock(),
            command=command,
            duration_ms=duration_ms,
            tokens=tokens,
            cost_usd=cost_usd,
            tool_calls=tool_calls,
            success=success,
            error=error,
        )
        item: dict[str, Any] = {
            "PK": f"JOB#{metric.job_id}",
            "SK": f"METRIC#{metric.ts}",
            "GSI2PK": f"METRIC#{_day_of(metric.ts)}",
            "GSI2SK": metric.ts,
            "job_id": metric.job_id,
            "ts": metric.ts,
            "command": metric.command,
            "success": metric.success,
        }
        optional = {
            "duration_ms": metric.duration_ms,
            "tokens": metric.tokens,
            "cost_usd": metric.cost_usd,
            "tool_calls": metric.tool_calls,
            "error": metric.error,
        }
        for key, value in optional.items():
            if value is not None:
                item[key] = _encode(value)
        self._table.put_item(Item=item)
        return metric

    def list_for_job(self, job_id: str, limit: int = 100) -> list[MetricRecord]:
        from boto3.dynamodb.conditions import Key  # lazy

        resp = self._table.query(
            KeyConditionExpression=(
                Key("PK").eq(f"JOB#{job_id}") & Key("SK").begins_with("METRIC#")
            ),
            ScanIndexForward=True,  # SK 가 METRIC#{ts} — 문자열 정렬 = 시간순
            Limit=limit,
        )
        return [_from_item(item) for item in resp.get("Items", [])]

    def list_feed(self, day: str | None = None, limit: int = 50) -> list[MetricRecord]:
        from boto3.dynamodb.conditions import Key  # lazy

        day = day or _day_of(self._clock())
        resp = self._table.query(
            IndexName="GSI2",
            KeyConditionExpression=Key("GSI2PK").eq(f"METRIC#{day}"),
            ScanIndexForward=False,  # 최신순
            Limit=limit,
        )
        return [_from_item(item) for item in resp.get("Items", [])]


def _from_item(item: dict[str, Any]) -> MetricRecord:
    duration = item.get("duration_ms")
    tokens = item.get("tokens")
    cost = item.get("cost_usd")
    tool_calls = item.get("tool_calls")
    return MetricRecord(
        job_id=item["job_id"],
        ts=item["ts"],
        command=item.get("command", ""),
        duration_ms=float(duration) if duration is not None else None,
        tokens=int(tokens) if tokens is not None else None,
        cost_usd=float(cost) if cost is not None else None,
        tool_calls=int(tool_calls) if tool_calls is not None else None,
        success=bool(item.get("success", True)),
        error=item.get("error"),
    )
