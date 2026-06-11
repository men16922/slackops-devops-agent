"""telemetry 테스트 — record_run_metrics 가 주입된 TelemetryStore 에 기록하는지.

실 OTel/ADOT 호출 없음 — setup_telemetry 는 lazy stub(미설치 시 None) 동작만 검증.
store 동치(Sqlite vs DynamoDb)는 test_audit_telemetry_store.py 가 담당하므로
여기서는 Sqlite in-memory 로 기록 경로만 본다.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from app.store import SqliteTelemetryStore
from app.telemetry import record_run_metrics, setup_telemetry


@pytest.fixture
def store() -> Iterator[SqliteTelemetryStore]:
    from tests._helpers import counter_clock

    s = SqliteTelemetryStore(":memory:", clock=counter_clock())
    yield s
    s.close()


def test_record_run_metrics_writes_to_injected_store(store: SqliteTelemetryStore) -> None:
    metric = record_run_metrics(
        store,
        "job-1",
        command="diagnose",
        duration_ms=1234.5,
        tokens=4200,
        cost_usd=0.0312,
        tool_calls=3,
    )

    stored = store.list_for_job("job-1")
    assert stored == [metric]
    assert stored[0].command == "diagnose"
    assert stored[0].duration_ms == 1234.5
    assert stored[0].tokens == 4200
    assert stored[0].cost_usd == 0.0312
    assert stored[0].tool_calls == 3
    assert stored[0].success is True
    assert stored[0].error is None


def test_record_run_metrics_failure_keeps_error(store: SqliteTelemetryStore) -> None:
    record_run_metrics(
        store,
        "job-2",
        command="logs",
        success=False,
        error="claude headless timed out after 300s",
    )

    [stored] = store.list_for_job("job-2")
    assert stored.success is False
    assert stored.error == "claude headless timed out after 300s"


def test_record_run_metrics_minimal_args_defaults(store: SqliteTelemetryStore) -> None:
    metric = record_run_metrics(store, "job-3")

    [stored] = store.list_for_job("job-3")
    assert stored == metric
    assert stored.command == ""
    assert stored.duration_ms is None
    assert stored.tokens is None
    assert stored.cost_usd is None
    assert stored.tool_calls is None
    assert stored.success is True


def test_record_run_metrics_appears_in_day_feed(store: SqliteTelemetryStore) -> None:
    record_run_metrics(store, "job-1", command="ping")
    record_run_metrics(store, "job-2", command="logs")

    feed = store.list_feed("20260612")
    assert [m.command for m in feed] == ["logs", "ping"]  # 최신순


def test_setup_telemetry_lazy_stub_import_safe() -> None:
    """SDK 설치 여부와 무관하게 raise 없이 동작 — 미설치면 None."""
    try:
        import opentelemetry  # noqa: F401

        installed = True
    except ImportError:
        installed = False

    tracer = setup_telemetry()
    if installed:
        assert tracer is not None
    else:
        assert tracer is None
