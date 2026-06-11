"""테스트 공용 헬퍼 — 주입용 mock 실행기/fetcher 와 result JSON 빌더.

claude_runner/allowlist/logs/diagnose 테스트가 동일한 mock 을 복붙하지 않도록 한 곳에 둔다.
(test_ prefix 가 없어 pytest 가 테스트로 수집하지 않는다.)
"""

from __future__ import annotations

import json
from collections.abc import Callable


class RecordingRunner:
    """주입용 mock subprocess 실행기 — 호출 (cmd, timeout_s) 를 기록하고 고정 응답 반환.

    SubprocessRunner 규약과 동일하게 (exit_code, stdout, stderr) 를 돌려준다.
    """

    def __init__(self, stdout: str = "", exit_code: int = 0, stderr: str = "") -> None:
        self.stdout = stdout
        self.exit_code = exit_code
        self.stderr = stderr
        self.calls: list[tuple[list[str], int]] = []

    def __call__(self, cmd: list[str], timeout_s: int) -> tuple[int, str, str]:
        self.calls.append((cmd, timeout_s))
        return self.exit_code, self.stdout, self.stderr


class RecordingFetcher:
    """주입용 mock 소스 fetcher — 호출 service 를 기록하고 고정 내용 반환."""

    def __init__(self, content: str = "INFO ok") -> None:
        self.content = content
        self.calls: list[str] = []

    def __call__(self, service: str) -> str:
        self.calls.append(service)
        return self.content


def result_json(result: str = "ok", cost: float = 0.01) -> str:
    """claude `--output-format json` 성공 출력의 최소 형태(result + 비용)."""
    return json.dumps({"result": result, "total_cost_usd": cost})


# ── store 테스트 공용 (test_store / test_audit_telemetry_store) ──


def counter_clock() -> Callable[[], str]:
    """호출마다 1초씩 전진하는 결정적 clock(같은 날 안에서 단조 증가)."""
    state = {"i": 0}

    def clock() -> str:
        state["i"] += 1
        return f"2026-06-12T00:00:{state['i']:02d}.000000Z"

    return clock


def counter_id() -> Callable[[], str]:
    """job-1, job-2, … 결정적 id factory."""
    state = {"i": 0}

    def idf() -> str:
        state["i"] += 1
        return f"job-{state['i']}"

    return idf


def create_single_table(dynamodb: object, table_name: str) -> None:
    """제출 데이터모델대로 단일테이블 + GSI1/GSI2 생성(deploy provisioning 과 동일 스키마)."""
    dynamodb.create_table(  # type: ignore[attr-defined]
        TableName=table_name,
        BillingMode="PAY_PER_REQUEST",
        KeySchema=[
            {"AttributeName": "PK", "KeyType": "HASH"},
            {"AttributeName": "SK", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "PK", "AttributeType": "S"},
            {"AttributeName": "SK", "AttributeType": "S"},
            {"AttributeName": "GSI1PK", "AttributeType": "S"},
            {"AttributeName": "GSI1SK", "AttributeType": "S"},
            {"AttributeName": "GSI2PK", "AttributeType": "S"},
            {"AttributeName": "GSI2SK", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "GSI1",
                "KeySchema": [
                    {"AttributeName": "GSI1PK", "KeyType": "HASH"},
                    {"AttributeName": "GSI1SK", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
            {
                "IndexName": "GSI2",
                "KeySchema": [
                    {"AttributeName": "GSI2PK", "KeyType": "HASH"},
                    {"AttributeName": "GSI2SK", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
        ],
    )
