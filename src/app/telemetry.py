"""실행 계측 — record_run_metrics 가 주입된 TelemetryStore 에 metric 기록.

H0 이중 컨트롤플레인에서 지표의 source of truth 는 단일테이블 Metric 항목이다
(store/telemetry_store.py — Sqlite 로컬/테스트, DynamoDb 운영, 대시보드 피드 공유).
OTel SDK → ADOT Collector → CloudWatch 파이프라인은 Day 8–9 에 결합하며,
setup_telemetry 는 그때까지 lazy stub — SDK 미설치 환경에서도 import-safe 하고
미설치면 None 을 반환한다(호출부는 None 이면 trace 생략).
"""

from __future__ import annotations

from typing import Any

from app.store import MetricRecord, TelemetryStore


def setup_telemetry(service_name: str = "slackops-devops-agent") -> Any | None:
    """OTel tracer 획득 — lazy stub.

    TracerProvider + OTLP exporter(→ ADOT Collector) 셋업은 Day 8–9 에 구현한다.
    지금은 SDK 가 설치돼 있으면 기본 tracer 를, 미설치면 None 을 반환한다.

    Args:
        service_name: 리소스 service.name 속성(tracer 이름으로 사용).

    Returns:
        OTel tracer, 또는 opentelemetry 미설치 시 None.
    """
    try:
        from opentelemetry import trace  # lazy: 미설치 환경 import-safe
    except ImportError:
        return None
    return trace.get_tracer(service_name)


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
) -> MetricRecord:
    """에이전트 실행 1건의 계측 지표를 주입된 store 에 기록.

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

    Returns:
        기록된 MetricRecord(ts 는 store clock 이 부여).
    """
    return store.record(
        job_id,
        command=command,
        duration_ms=duration_ms,
        tokens=tokens,
        cost_usd=cost_usd,
        tool_calls=tool_calls,
        success=success,
        error=error,
    )
