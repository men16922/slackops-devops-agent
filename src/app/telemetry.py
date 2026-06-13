"""실행 계측 — record_run_metrics 가 주입된 TelemetryStore 에 기록 (+선택 OTel emit).

H0 이중 컨트롤플레인에서 지표의 source of truth 는 단일테이블 Metric 항목이다
(store/telemetry_store.py — Sqlite 로컬/테스트, DynamoDb 운영, 대시보드 피드 공유).
OTel 은 부가 파이프라인: setup_telemetry 가 TracerProvider(+OTLP → ADOT Collector)를
구성해 tracer 를 돌려주고, record_run_metrics 는 tracer 가 주입된 경우에만 실행 1건을
span 으로 추가 emit 한다. opentelemetry 미설치 환경에서도 전 경로 import-safe.
"""

from __future__ import annotations

from typing import Any

from app.store import MetricRecord, TelemetryStore

_DEFAULT_OTLP_ENDPOINT = "http://127.0.0.1:4317"  # 같은 호스트의 ADOT Collector gRPC


def setup_telemetry(
    service_name: str = "slackops-devops-agent",
    *,
    span_exporter: Any | None = None,
    otlp_endpoint: str = _DEFAULT_OTLP_ENDPOINT,
) -> Any | None:
    """OTel tracer 구성 — TracerProvider + span exporter.

    exporter 는 주입 가능(테스트 = InMemorySpanExporter). 미주입이면 OTLP gRPC
    exporter(→ ADOT Collector)를 lazy 구성한다. SDK 또는 OTLP exporter 패키지가
    없으면 None 을 반환하고, 호출부는 None 이면 OTel emit 만 생략한다(store 기록은 유지).

    SimpleSpanProcessor 채택 이유: Slack 명령 단위 저볼륨이라 동기 export 로 충분하고,
    수명이 짧은 헤드리스 프로세스에서 batch flush 타이밍에 따른 유실이 없다.

    Args:
        service_name: Resource `service.name` 속성(tracer 이름으로도 사용).
        span_exporter: 주입 exporter(테스트용). None 이면 OTLP gRPC exporter 구성.
        otlp_endpoint: OTLP gRPC 수신 endpoint(기본 = 로컬 ADOT Collector).

    Returns:
        구성된 tracer, 또는 SDK/exporter 미설치 시 None.
    """
    try:
        from opentelemetry.sdk.resources import Resource  # lazy: 미설치 환경 import-safe
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    except ImportError:
        return None
    if span_exporter is None:
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                OTLPSpanExporter,
            )
        except ImportError:
            return None
        span_exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    provider.add_span_processor(SimpleSpanProcessor(span_exporter))
    return provider.get_tracer(service_name)


def record_run_metrics(
    store: TelemetryStore,
    job_id: str,
    *,
    command: str = "",
    duration_ms: float | None = None,
    tokens: int | None = None,
    cost_usd: float | None = None,
    tool_calls: int | None = None,
    success: bool = True,
    error: str | None = None,
    tracer: Any | None = None,
) -> MetricRecord:
    """에이전트 실행 1건의 계측 지표를 주입된 store 에 기록(+tracer 있으면 OTel span emit).

    tool_calls 는 RunResult 가 제공하지 않으므로(claude_runner 참조) 호출부가
    별도로 전달한다 — stream-json 파싱 도입 전까지 None 허용.

    Args:
        store: 기록 대상 TelemetryStore(주입 — 테스트는 Sqlite, 운영은 DynamoDb).
        job_id: 대상 job 식별자.
        command: 실행된 subcommand(ping/logs/diagnose/...).
        duration_ms: end-to-end 실행 latency.
        tokens: 사용 토큰 수(input+output).
        cost_usd: 호출당 비용 USD.
        tool_calls: tool call 횟수.
        success: 성공 여부(실패율 집계용).
        error: 실패 사유(success=False 일 때).
        tracer: setup_telemetry 가 돌려준 tracer. None 이면 OTel emit 생략.

    Returns:
        기록된 MetricRecord(ts 는 store clock 이 부여).
    """
    record = store.record(
        job_id,
        command=command,
        duration_ms=duration_ms,
        tokens=tokens,
        cost_usd=cost_usd,
        tool_calls=tool_calls,
        success=success,
        error=error,
    )
    if tracer is not None:
        with tracer.start_as_current_span("devops.run") as span:
            span.set_attribute("devops.job_id", job_id)
            span.set_attribute("devops.command", command)
            span.set_attribute("devops.success", success)
            for key, value in (
                ("devops.duration_ms", duration_ms),
                ("devops.tokens", tokens),
                ("devops.cost_usd", cost_usd),
                ("devops.tool_calls", tool_calls),
                ("devops.error", error),
            ):
                if value is not None:  # OTel 속성은 None 불허 — 미수집 지표는 생략
                    span.set_attribute(key, value)
    return record
