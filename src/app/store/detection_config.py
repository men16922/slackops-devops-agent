"""Detection 토글 store — 거버넌스 탐지 카테고리의 ON/OFF·모드 설정(단일테이블 Config 항목).

키 설계(Job/Audit/Telemetry 와 같은 `slackops-agent` 테이블 공존):
  Config  PK=CONFIG#detections  SK={category}  GSI2=CONFIG#detections/{category}

대시보드(web/lib/ddb.ts)가 토글을 쓰고, 상주 모니터의 스케줄러(agent_monitor)가 enabled +
mode=scheduled 카테고리를 읽어 detect 작업을 큐에 적재한다 — **테이블이 거버넌스 커버리지의
컨트롤 플레인**. 구현은 주입 가능(Protocol) — 로컬/테스트 Sqlite, 운영 DynamoDb. boto3 는
lazy import 로 미설치 환경 import-safe.
"""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from app.store._util import utcnow_iso as _utcnow_iso

# 단일테이블 Config 항목 키.
CONFIG_PK = "CONFIG#detections"

# 모드: 온디맨드(대시보드 "Scan now")만 / 스케줄(상주 모니터가 주기 적재).
MODE_ON_DEMAND = "on-demand"
MODE_SCHEDULED = "scheduled"


@dataclass
class DetectionConfig:
    """탐지 카테고리 1개의 설정.

    Attributes:
        category: 카테고리 키(iam/config/ssm/incident).
        enabled: 활성 여부.
        mode: on-demand | scheduled.
        updated_at: 마지막 갱신 ISO8601 UTC.
        last_scan: 마지막 스캔 적재 시각(없으면 None).
    """

    category: str
    enabled: bool
    mode: str = MODE_ON_DEMAND
    updated_at: str = ""
    last_scan: str | None = None


class DetectionConfigStore(Protocol):
    """탐지 토글 저장소 인터페이스."""

    def set_config(
        self, category: str, *, enabled: bool, mode: str = MODE_ON_DEMAND
    ) -> DetectionConfig:
        """카테고리 설정 upsert."""
        ...

    def get_config(self, category: str) -> DetectionConfig | None:
        """카테고리 설정 조회(없으면 None)."""
        ...

    def list_configs(self) -> list[DetectionConfig]:
        """전체 카테고리 설정(카테고리명 오름차순)."""
        ...


# ── SQLite 구현 (로컬/테스트) ─────────────────────────────────

_SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS detection_config (
    category   TEXT PRIMARY KEY,
    enabled    INTEGER NOT NULL DEFAULT 0,
    mode       TEXT NOT NULL DEFAULT 'on-demand',
    updated_at TEXT NOT NULL DEFAULT '',
    last_scan  TEXT
);
"""


class SqliteDetectionConfigStore:
    """SQLite 기반 — DynamoDB put_item 덮어쓰기와 동치(INSERT OR REPLACE)."""

    def __init__(
        self, db_path: str = ":memory:", *, clock: Callable[[], str] | None = None
    ) -> None:
        self._clock = clock or _utcnow_iso
        self._conn = sqlite3.connect(db_path, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SQLITE_SCHEMA)

    def close(self) -> None:
        self._conn.close()

    def set_config(
        self, category: str, *, enabled: bool, mode: str = MODE_ON_DEMAND
    ) -> DetectionConfig:
        cfg = DetectionConfig(
            category=category, enabled=enabled, mode=mode, updated_at=self._clock()
        )
        self._conn.execute(
            "INSERT OR REPLACE INTO detection_config (category, enabled, mode, updated_at, last_scan) "
            "VALUES (?, ?, ?, ?, ?)",
            (cfg.category, int(cfg.enabled), cfg.mode, cfg.updated_at, cfg.last_scan),
        )
        return cfg

    def get_config(self, category: str) -> DetectionConfig | None:
        row = self._conn.execute(
            "SELECT category, enabled, mode, updated_at, last_scan FROM detection_config "
            "WHERE category = ?",
            (category,),
        ).fetchone()
        return _from_sqlite_row(row) if row is not None else None

    def list_configs(self) -> list[DetectionConfig]:
        rows = self._conn.execute(
            "SELECT category, enabled, mode, updated_at, last_scan FROM detection_config "
            "ORDER BY category"
        ).fetchall()
        return [_from_sqlite_row(row) for row in rows]


def _from_sqlite_row(row: sqlite3.Row) -> DetectionConfig:
    return DetectionConfig(
        category=row["category"],
        enabled=bool(row["enabled"]),
        mode=row["mode"],
        updated_at=row["updated_at"],
        last_scan=row["last_scan"],
    )


# ── DynamoDB 구현 (운영 — 단일테이블 공존) ────────────────────


class DynamoDbDetectionConfigStore:
    """DynamoDB 단일테이블 — 대시보드(TS)가 쓰는 같은 CONFIG#detections 항목을 읽고 쓴다."""

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

    def set_config(
        self, category: str, *, enabled: bool, mode: str = MODE_ON_DEMAND
    ) -> DetectionConfig:
        cfg = DetectionConfig(
            category=category, enabled=enabled, mode=mode, updated_at=self._clock()
        )
        item: dict[str, Any] = {
            "PK": CONFIG_PK,
            "SK": cfg.category,
            "GSI2PK": CONFIG_PK,
            "GSI2SK": cfg.category,
            "category": cfg.category,
            "enabled": cfg.enabled,
            "mode": cfg.mode,
            "updated_at": cfg.updated_at,
        }
        if cfg.last_scan is not None:
            item["last_scan"] = cfg.last_scan
        self._table.put_item(Item=item)
        return cfg

    def get_config(self, category: str) -> DetectionConfig | None:
        resp = self._table.get_item(Key={"PK": CONFIG_PK, "SK": category})
        item = resp.get("Item")
        return _from_item(item) if item else None

    def list_configs(self) -> list[DetectionConfig]:
        from boto3.dynamodb.conditions import Key  # lazy

        resp = self._table.query(
            KeyConditionExpression=Key("PK").eq(CONFIG_PK),
            ScanIndexForward=True,  # SK=category 오름차순
        )
        return [_from_item(item) for item in resp.get("Items", [])]


def _from_item(item: dict[str, Any]) -> DetectionConfig:
    return DetectionConfig(
        category=item["category"],
        enabled=bool(item.get("enabled", False)),
        mode=item.get("mode", MODE_ON_DEMAND),
        updated_at=item.get("updated_at", ""),
        last_scan=item.get("last_scan"),
    )


def config_store_from_env() -> DetectionConfigStore:
    """환경에서 DynamoDb 토글 store 구성 — JobStore(store_from_env)와 같은 단일테이블.

    DDB_ENDPOINT 있으면 DynamoDB Local, 없으면 실 DynamoDB. boto3 lazy import.
    """
    import boto3  # lazy: 선택 의존성

    table = os.environ.get("DDB_TABLE", "slackops-agent")
    endpoint = os.environ.get("DDB_ENDPOINT")
    region = os.environ.get("AWS_REGION", "us-east-1")
    kwargs: dict[str, Any] = {"region_name": region}
    if endpoint:
        kwargs["endpoint_url"] = endpoint
    return DynamoDbDetectionConfigStore(table, dynamodb=boto3.resource("dynamodb", **kwargs))
