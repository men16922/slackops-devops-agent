"""store 공용 유틸 — 4개 store 모듈에 중복돼 있던 시간/파티션/인코딩 헬퍼 통합.

(2026-06-13 리뷰 회차 finding — sqlite/dynamodb/audit/telemetry 가 각자 정의하던
_utcnow_iso/_day_of/_encode 를 한 곳으로. 모듈들은 기존 이름으로 alias import 한다.)
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal


def utcnow_iso() -> str:
    """UTC 현재 시각의 ISO 문자열(마이크로초 포함) — store 기본 clock."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def day_of(ts: str) -> str:
    """ISO ts → 일자 파티션 키(yyyymmdd)."""
    return ts[:10].replace("-", "")


def encode_for_dynamodb(value: object) -> object:
    """DynamoDB 는 float 를 직접 못 받는다 — Decimal 로 변환(USD 값 왕복 안전)."""
    if isinstance(value, float):
        return Decimal(str(value))
    return value
