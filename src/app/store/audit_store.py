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
import hashlib
import json
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from app.store._util import day_of as _day_of, utcnow_iso as _utcnow_iso

_SEQ_PAD = 6  # SK 문자열 정렬용 zero-pad 자릿수


def _step_id(seq: int) -> str:
    """job 내에서 유일하고 결정적인 스텝 식별자 — 난수가 아니라 append 순서에서 유도한다."""
    return f"S{seq:0{_SEQ_PAD}d}"


@dataclass
class AuditEvent:
    """감사 이벤트 1건 — 누가(actor) 어떤 job 에 무엇을(action) 했는지.

    최종 응답만이 아니라 실행 궤적을 남긴다: step_id/parent_step_id 로 요청→계획→정책→승인→
    실행→결과를 부모/자식으로 재구성하고, tool_name/capabilities/target_resource/result_hash 로
    "무엇이 무슨 권한으로 어디에 무엇을 했는지"를 결과 본문 없이 증명한다.

    Attributes:
        job_id: 대상 job 식별자.
        ts: ISO8601 UTC 정렬 가능 문자열.
        seq: 같은 ts 내 정렬 안정용 tie-breaker.
        action: 이벤트 종류(enqueued/claimed/awaiting_approval/approved/...).
        actor: 행위자(Slack user / web user / worker).
        detail: 부가 설명(자유 텍스트).
        step_id: 이 이벤트의 안정 식별자(job 내 유일) — 다른 이벤트가 부모로 지목할 수 있다.
        parent_step_id: 이 스텝이 파생된 상위 스텝(없으면 루트). 예: 승인 후 발급된 write
            credential 스텝은 그것을 허가한 `approved` 스텝을 부모로 갖는다.
        tool_name: 이 스텝이 사용한 도구/명령.
        capabilities: 이 스텝이 행사한 capability(execution_plan taxonomy).
        target_resource: 대상 리소스(log_group:/aws/x, repo:owner/name 등).
        result_hash: 결과 본문의 sha256 — 본문을 저장하지 않고도 무엇이 반환됐는지 고정한다.
    """

    job_id: str
    ts: str
    seq: int
    action: str
    actor: str = ""
    detail: str = ""
    context: dict[str, str] = field(default_factory=dict)
    prev_event_hash: str = ""
    event_hash: str = ""
    step_id: str = ""
    parent_step_id: str = ""
    tool_name: str = ""
    capabilities: tuple[str, ...] = ()
    target_resource: str = ""
    result_hash: str = ""


class AuditStore(Protocol):
    """감사 이벤트 append-only 저장소 인터페이스 (수정/삭제 없음)."""

    def append(
        self,
        job_id: str,
        action: str,
        *,
        actor: str = "",
        detail: str = "",
        context: dict[str, str] | None = None,
        parent_step_id: str = "",
        tool_name: str = "",
        capabilities: tuple[str, ...] = (),
        target_resource: str = "",
        result_hash: str = "",
    ) -> AuditEvent:
        """이벤트 1건 추가. step_id 는 스토어가 부여한다(호출자가 정하지 않는다)."""
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
    context TEXT NOT NULL DEFAULT '{}',
    prev_event_hash TEXT NOT NULL DEFAULT '',
    event_hash TEXT NOT NULL DEFAULT '',
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
        self._ensure_hash_columns()

    def close(self) -> None:
        self._conn.close()

    def _ensure_hash_columns(self) -> None:
        existing = {row["name"] for row in self._conn.execute("PRAGMA table_info(audit_events)")}
        for name, definition in (
            ("context", "TEXT NOT NULL DEFAULT '{}'") ,
            ("prev_event_hash", "TEXT NOT NULL DEFAULT ''"),
            ("event_hash", "TEXT NOT NULL DEFAULT ''"),
            ("step_id", "TEXT NOT NULL DEFAULT ''"),
            ("parent_step_id", "TEXT NOT NULL DEFAULT ''"),
            ("tool_name", "TEXT NOT NULL DEFAULT ''"),
            ("capabilities", "TEXT NOT NULL DEFAULT ''"),
            ("target_resource", "TEXT NOT NULL DEFAULT ''"),
            ("result_hash", "TEXT NOT NULL DEFAULT ''"),
        ):
            if name not in existing:
                self._conn.execute(f"ALTER TABLE audit_events ADD COLUMN {name} {definition}")

    def append(
        self,
        job_id: str,
        action: str,
        *,
        actor: str = "",
        detail: str = "",
        context: dict[str, str] | None = None,
        parent_step_id: str = "",
        tool_name: str = "",
        capabilities: tuple[str, ...] = (),
        target_resource: str = "",
        result_hash: str = "",
    ) -> AuditEvent:
        previous = self._conn.execute(
            "SELECT event_hash FROM audit_events WHERE job_id = ? ORDER BY ts DESC, seq DESC LIMIT 1",
            (job_id,),
        ).fetchone()
        seq = next(self._seq)
        event = AuditEvent(
            job_id=job_id,
            ts=self._clock(),
            seq=seq,
            action=action,
            actor=actor,
            detail=detail,
            context=dict(context or {}),
            prev_event_hash=str(previous["event_hash"]) if previous else "",
            step_id=_step_id(seq),
            parent_step_id=parent_step_id,
            tool_name=tool_name,
            capabilities=tuple(capabilities),
            target_resource=target_resource,
            result_hash=result_hash,
        )
        event.event_hash = event_hash(event)
        self._conn.execute(
            "INSERT INTO audit_events (job_id, ts, seq, day, action, actor, detail, context, "
            "prev_event_hash, event_hash, step_id, parent_step_id, tool_name, capabilities, "
            "target_resource, result_hash) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                event.job_id,
                event.ts,
                event.seq,
                _day_of(event.ts),
                event.action,
                event.actor,
                event.detail,
                json.dumps(event.context, sort_keys=True, separators=(",", ":")),
                event.prev_event_hash,
                event.event_hash,
                event.step_id,
                event.parent_step_id,
                event.tool_name,
                ",".join(event.capabilities),
                event.target_resource,
                event.result_hash,
            ),
        )
        return event

    def list_for_job(self, job_id: str, limit: int = 100) -> list[AuditEvent]:
        rows = self._conn.execute(
            f"SELECT {_SQLITE_COLUMNS} FROM audit_events WHERE job_id = ? ORDER BY ts, seq LIMIT ?",
            (job_id, limit),
        ).fetchall()
        return [_from_sqlite_row(row) for row in rows]

    def list_feed(self, day: str | None = None, limit: int = 50) -> list[AuditEvent]:
        day = day or _day_of(self._clock())
        rows = self._conn.execute(
            f"SELECT {_SQLITE_COLUMNS} FROM audit_events WHERE day = ? ORDER BY ts DESC, seq DESC LIMIT ?",
            (day, limit),
        ).fetchall()
        return [_from_sqlite_row(row) for row in rows]


_SQLITE_COLUMNS = (
    "job_id, ts, seq, action, actor, detail, context, prev_event_hash, event_hash, "
    "step_id, parent_step_id, tool_name, capabilities, target_resource, result_hash"
)


def _from_sqlite_row(row: sqlite3.Row) -> AuditEvent:
    raw_capabilities = row["capabilities"] or ""
    return AuditEvent(
        job_id=row["job_id"],
        ts=row["ts"],
        seq=row["seq"],
        action=row["action"],
        actor=row["actor"],
        detail=row["detail"],
        context=_context_from_json(row["context"]),
        prev_event_hash=row["prev_event_hash"],
        event_hash=row["event_hash"],
        step_id=row["step_id"],
        parent_step_id=row["parent_step_id"],
        tool_name=row["tool_name"],
        capabilities=tuple(c for c in raw_capabilities.split(",") if c),
        target_resource=row["target_resource"],
        result_hash=row["result_hash"],
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
        self,
        job_id: str,
        action: str,
        *,
        actor: str = "",
        detail: str = "",
        context: dict[str, str] | None = None,
        parent_step_id: str = "",
        tool_name: str = "",
        capabilities: tuple[str, ...] = (),
        target_resource: str = "",
        result_hash: str = "",
    ) -> AuditEvent:
        from boto3.dynamodb.conditions import Key  # lazy

        previous = self._table.query(
            KeyConditionExpression=(
                Key("PK").eq(f"JOB#{job_id}") & Key("SK").begins_with("AUDIT#")
            ),
            ScanIndexForward=False,
            Limit=1,
        ).get("Items", [])
        seq = next(self._seq)
        event = AuditEvent(
            job_id=job_id,
            ts=self._clock(),
            seq=seq,
            action=action,
            actor=actor,
            detail=detail,
            context=dict(context or {}),
            prev_event_hash=str(previous[0].get("event_hash", "")) if previous else "",
            step_id=_step_id(seq),
            parent_step_id=parent_step_id,
            tool_name=tool_name,
            capabilities=tuple(capabilities),
            target_resource=target_resource,
            result_hash=result_hash,
        )
        event.event_hash = event_hash(event)
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
                "context": event.context,
                "prev_event_hash": event.prev_event_hash,
                "event_hash": event.event_hash,
                "step_id": event.step_id,
                "parent_step_id": event.parent_step_id,
                "tool_name": event.tool_name,
                "capabilities": list(event.capabilities),
                "target_resource": event.target_resource,
                "result_hash": event.result_hash,
            },
            ConditionExpression="attribute_not_exists(PK) AND attribute_not_exists(SK)",
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
        context={str(key): str(value) for key, value in item.get("context", {}).items()},
        prev_event_hash=item.get("prev_event_hash", ""),
        event_hash=item.get("event_hash", ""),
        step_id=item.get("step_id", ""),
        parent_step_id=item.get("parent_step_id", ""),
        tool_name=item.get("tool_name", ""),
        capabilities=tuple(str(c) for c in item.get("capabilities", [])),
        target_resource=item.get("target_resource", ""),
        result_hash=item.get("result_hash", ""),
    )


def _context_from_json(value: str) -> dict[str, str]:
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return {}
    if not isinstance(parsed, dict):
        return {}
    return {str(key): str(item) for key, item in parsed.items()}


def event_hash(event: AuditEvent) -> str:
    """Return a stable hash over one event, its trajectory fields, and its predecessor.

    Trajectory fields join the payload **only when set**. Events written before those
    fields existed hash exactly as they did then, so `verify_event_chain` still passes
    over records already in DynamoDB — tamper-evidence would be worthless if a schema
    change silently invalidated every historical chain.
    """
    payload: dict[str, Any] = {
        "job_id": event.job_id,
        "ts": event.ts,
        "seq": event.seq,
        "action": event.action,
        "actor": event.actor,
        "detail": event.detail,
        "context": event.context,
        "prev_event_hash": event.prev_event_hash,
    }
    trajectory: dict[str, Any] = {
        "step_id": event.step_id,
        "parent_step_id": event.parent_step_id,
        "tool_name": event.tool_name,
        "capabilities": list(event.capabilities),
        "target_resource": event.target_resource,
        "result_hash": event.result_hash,
    }
    payload.update({key: value for key, value in trajectory.items() if value})
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def result_digest(result: str) -> str:
    """Hash a step's result so the trail can prove it without storing the body."""
    return hashlib.sha256(result.encode("utf-8")).hexdigest()


def build_step_tree(events: list[AuditEvent]) -> dict[str, list[AuditEvent]]:
    """Group a job's events by parent, so the trajectory can be walked as a tree.

    Roots are keyed by "". Events without a step_id (pre-trajectory records) are ignored
    rather than silently reparented.
    """
    tree: dict[str, list[AuditEvent]] = {}
    for event in events:
        if not event.step_id:
            continue
        tree.setdefault(event.parent_step_id, []).append(event)
    return tree


def verify_event_chain(events: list[AuditEvent]) -> bool:
    """Check chronological audit events for hash integrity and predecessor linkage."""
    previous = ""
    for event in events:
        if event.prev_event_hash != previous or event.event_hash != event_hash(event):
            return False
        previous = event.event_hash
    return True
