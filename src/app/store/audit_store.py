"""Audit store — job 별 감사 이벤트 append-only 기록 (단일테이블 Audit 항목).

키 설계(docs/plans/2026-06-12-h0-hackathon.md, DECISIONS D5):
  Audit  PK=JOB#{id}  SK=AUDIT#{ts}#{seq}  GSI2=AUDIT#{yyyymmdd}/{ts}
job 단위 추적(list_for_job)과 일자별 피드(list_feed — 대시보드)를 모두 지원한다.

구현은 주입 가능(AuditStore 프로토콜) — 로컬/테스트 SqliteAuditStore, 운영 DynamoDbAuditStore.
boto3 는 lazy import 로 미설치 환경에서도 모듈 import-safe. seq 는 같은 ts 충돌 시
정렬 안정용 tie-breaker(스토어 인스턴스 단위 단조 증가, SK 에 zero-pad 로 문자열 정렬 보장).
"""

from __future__ import annotations

import itertools
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

_SEQ_PAD = 6  # SK 문자열 정렬용 zero-pad 자릿수


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _day_of(ts: str) -> str:
    """ISO ts → 일자 파티션 키(yyyymmdd)."""
    return ts[:10].replace("-", "")


@dataclass
class AuditEvent:
    """감사 이벤트 1건 — 누가(actor) 어떤 job 에 무엇을(action) 했는지.

    Attributes:
        job_id: 대상 job 식별자.
        ts: ISO8601 UTC 정렬 가능 문자열.
        seq: 같은 ts 내 정렬 안정용 tie-breaker.
        action: 이벤트 종류(enqueued/claimed/awaiting_approval/approved/...).
        actor: 행위자(Slack user / web user / worker).
        detail: 부가 설명(자유 텍스트).
    """

    job_id: str
    ts: str
    seq: int
    action: str
    actor: str = ""
    detail: str = ""


class AuditStore(Protocol):
    """감사 이벤트 append-only 저장소 인터페이스 (수정/삭제 없음)."""

    def append(
        self, job_id: str, action: str, *, actor: str = "", detail: str = ""
    ) -> AuditEvent:
        """이벤트 1건 추가."""
        ...

    def list_for_job(self, job_id: str, limit: int = 100) -> list[AuditEvent]:
        """job 1건의 이벤트를 시간순(오래된 것부터)으로."""
        ...

    def list_feed(self, day: str | None = None, limit: int = 50) -> list[AuditEvent]:
        """일자(yyyymmdd, 기본=현재 clock 일자) 피드를 최신순으로(대시보드용)."""
        ...


# ── SQLite 구현 (로컬/테스트) ─────────────────────────────────

_SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_events (
    job_id TEXT NOT NULL,
    ts     TEXT NOT NULL,
    seq    INTEGER NOT NULL,
    day    TEXT NOT NULL,
    action TEXT NOT NULL,
    actor  TEXT NOT NULL DEFAULT '',
    detail TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (job_id, ts, seq)
);
CREATE INDEX IF NOT EXISTS idx_audit_day_ts ON audit_events(day, ts);
"""


class SqliteAuditStore:
    """SQLite 기반 AuditStore 구현 — DynamoDB put_item 덮어쓰기와 동치(INSERT OR REPLACE)."""

    def __init__(
        self,
        db_path: str = ":memory:",
        *,
        clock: Callable[[], str] | None = None,
    ) -> None:
        self._clock = clock or _utcnow_iso
        self._seq = itertools.count(1)
        self._conn = sqlite3.connect(db_path, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SQLITE_SCHEMA)

    def close(self) -> None:
        self._conn.close()

    def append(
        self, job_id: str, action: str, *, actor: str = "", detail: str = ""
    ) -> AuditEvent:
        event = AuditEvent(
            job_id=job_id,
            ts=self._clock(),
            seq=next(self._seq),
            action=action,
            actor=actor,
            detail=detail,
        )
        self._conn.execute(
            "INSERT OR REPLACE INTO audit_events (job_id, ts, seq, day, action, actor, detail) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (event.job_id, event.ts, event.seq, _day_of(event.ts), event.action, event.actor, event.detail),
        )
        return event

    def list_for_job(self, job_id: str, limit: int = 100) -> list[AuditEvent]:
        rows = self._conn.execute(
            "SELECT job_id, ts, seq, action, actor, detail FROM audit_events "
            "WHERE job_id = ? ORDER BY ts, seq LIMIT ?",
            (job_id, limit),
        ).fetchall()
        return [_from_sqlite_row(row) for row in rows]

    def list_feed(self, day: str | None = None, limit: int = 50) -> list[AuditEvent]:
        day = day or _day_of(self._clock())
        rows = self._conn.execute(
            "SELECT job_id, ts, seq, action, actor, detail FROM audit_events "
            "WHERE day = ? ORDER BY ts DESC, seq DESC LIMIT ?",
            (day, limit),
        ).fetchall()
        return [_from_sqlite_row(row) for row in rows]


def _from_sqlite_row(row: sqlite3.Row) -> AuditEvent:
    return AuditEvent(
        job_id=row["job_id"],
        ts=row["ts"],
        seq=row["seq"],
        action=row["action"],
        actor=row["actor"],
        detail=row["detail"],
    )


# ── DynamoDB 구현 (운영 — JobStore 와 같은 단일테이블) ─────────


class DynamoDbAuditStore:
    """DynamoDB 단일테이블 AuditStore 구현 (Job META 항목과 같은 테이블 공존)."""

    def __init__(
        self,
        table_name: str = "slackops-agent",
        *,
        dynamodb: Any | None = None,
        clock: Callable[[], str] | None = None,
    ) -> None:
        self._clock = clock or _utcnow_iso
        self._seq = itertools.count(1)
        if dynamodb is None:
            import boto3  # lazy: 미설치/자격증명 없는 환경 import-safe

            dynamodb = boto3.resource("dynamodb")
        self._table = dynamodb.Table(table_name)

    def append(
        self, job_id: str, action: str, *, actor: str = "", detail: str = ""
    ) -> AuditEvent:
        event = AuditEvent(
            job_id=job_id,
            ts=self._clock(),
            seq=next(self._seq),
            action=action,
            actor=actor,
            detail=detail,
        )
        self._table.put_item(
            Item={
                "PK": f"JOB#{event.job_id}",
                "SK": f"AUDIT#{event.ts}#{event.seq:0{_SEQ_PAD}d}",
                "GSI2PK": f"AUDIT#{_day_of(event.ts)}",
                "GSI2SK": event.ts,
                "job_id": event.job_id,
                "ts": event.ts,
                "seq": event.seq,
                "action": event.action,
                "actor": event.actor,
                "detail": event.detail,
            }
        )
        return event

    def list_for_job(self, job_id: str, limit: int = 100) -> list[AuditEvent]:
        from boto3.dynamodb.conditions import Key  # lazy

        resp = self._table.query(
            KeyConditionExpression=(
                Key("PK").eq(f"JOB#{job_id}") & Key("SK").begins_with("AUDIT#")
            ),
            ScanIndexForward=True,  # SK 가 ts#seq(zero-pad) — 문자열 정렬 = 시간순
            Limit=limit,
        )
        return [_from_item(item) for item in resp.get("Items", [])]

    def list_feed(self, day: str | None = None, limit: int = 50) -> list[AuditEvent]:
        from boto3.dynamodb.conditions import Key  # lazy

        day = day or _day_of(self._clock())
        resp = self._table.query(
            IndexName="GSI2",
            KeyConditionExpression=Key("GSI2PK").eq(f"AUDIT#{day}"),
            ScanIndexForward=False,  # 최신순
            Limit=limit,
        )
        return [_from_item(item) for item in resp.get("Items", [])]


def _from_item(item: dict[str, Any]) -> AuditEvent:
    return AuditEvent(
        job_id=item["job_id"],
        ts=item["ts"],
        seq=int(item["seq"]),
        action=item["action"],
        actor=item.get("actor", ""),
        detail=item.get("detail", ""),
    )
