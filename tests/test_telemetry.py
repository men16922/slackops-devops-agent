"""telemetry 테스트 — record_run_metrics 의 store 기록 + 선택적 OTel span emit.

실 OTLP/ADOT 호출 없음 — OTel 경로는 InMemorySpanExporter 주입으로만 검증하고,
SDK 미설치 환경에서는 해당 테스트를 skip(나머지는 import-safe 그대로 통과).
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


def test_setup_telemetry_import_safe_without_exporter_injection() -> None:
    """SDK/exporter 설치 여부와 무관하게 raise 없이 동작.

    OTLP exporter 패키지까지 있어야 tracer, 하나라도 없으면 None — 어느 쪽이든
    예외가 아니어야 한다(미설치 환경 import-safe 불변).
    """
    try:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (  # noqa: F401
            OTLPSpanExporter,
        )

        otlp_installed = True
    except ImportError:
        otlp_installed = False

    tracer = setup_telemetry()
    if otlp_installed:
        assert tracer is not None
    else:
        assert tracer is None


def _in_memory_tracer() -> tuple[object, object]:
    """(tracer, exporter) — SDK 미설치 환경이면 테스트 skip."""
    pytest.importorskip("opentelemetry.sdk")
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
        InMemorySpanExporter,
    )

    exporter = InMemorySpanExporter()
    tracer = setup_telemetry(span_exporter=exporter)
    assert tracer is not None
    return tracer, exporter


def test_setup_telemetry_builds_pipeline_with_injected_exporter() -> None:
    tracer, exporter = _in_memory_tracer()

    with tracer.start_as_current_span("probe"):  # type: ignore[attr-defined]
        pass

    [span] = exporter.get_finished_spans()  # type: ignore[attr-defined]
    assert span.name == "probe"
    assert span.resource.attributes["service.name"] == "slackops-devops-agent"


def test_record_run_metrics_emits_otel_span_with_attributes(
    store: SqliteTelemetryStore,
) -> None:
    tracer, exporter = _in_memory_tracer()

    metric = record_run_metrics(
        store,
        "job-otel",
        command="diagnose",
        duration_ms=1234.5,
        tokens=4200,
        cost_usd=0.0312,
        tool_calls=3,
        tracer=tracer,
    )

    assert store.list_for_job("job-otel") == [metric]  # store 기록은 그대로
    [span] = exporter.get_finished_spans()  # type: ignore[attr-defined]
    assert span.name == "devops.run"
    attrs = dict(span.attributes)
    assert attrs["devops.job_id"] == "job-otel"
    assert attrs["devops.command"] == "diagnose"
    assert attrs["devops.success"] is True
    assert attrs["devops.duration_ms"] == 1234.5
    assert attrs["devops.tokens"] == 4200
    assert attrs["devops.cost_usd"] == 0.0312
    assert attrs["devops.tool_calls"] == 3
    assert "devops.error" not in attrs


def test_record_run_metrics_otel_span_failure_keeps_error(
    store: SqliteTelemetryStore,
) -> None:
    tracer, exporter = _in_memory_tracer()

    record_run_metrics(
        store,
        "job-otel-fail",
        command="logs",
        success=False,
        error="claude headless timed out after 300s",
        tracer=tracer,
    )

    [span] = exporter.get_finished_spans()  # type: ignore[attr-defined]
    attrs = dict(span.attributes)
    assert attrs["devops.success"] is False
    assert attrs["devops.error"] == "claude headless timed out after 300s"
    assert "devops.duration_ms" not in attrs  # None 지표는 속성 생략


def test_record_run_metrics_without_tracer_skips_otel(
    store: SqliteTelemetryStore,
) -> None:
    """tracer 미주입(=None) 이면 store 기록만 — OTel 의존 없음(기본 경로 불변)."""
    metric = record_run_metrics(store, "job-plain", command="ping")
    assert store.list_for_job("job-plain") == [metric]
