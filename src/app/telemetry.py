"""OTel SDK 셋업 — OTel SDK → ADOT Collector → CloudWatch.

실행 1건당 step latency / 토큰 / 비용(USD) / tool call 횟수·종류·실패율 / E2E p50·p95 계측.
Trace 는 발표·아티클 수치 확보 목적.
"""

from __future__ import annotations

from typing import Any


def setup_telemetry(service_name: str = "slackops-devops-agent") -> Any:
    """OTel TracerProvider + OTLP exporter(→ ADOT Collector) 초기화.

    Args:
        service_name: 리소스 service.name 속성.

    Returns:
        설정된 Tracer (stub: 미구현).
    """
    raise NotImplementedError("Day 8–9: OTel SDK → ADOT 파이프라인 구현 예정")


def record_run_metrics(
    *,
    step_latencies_ms: dict[str, float],
    tokens: int | None,
    cost_usd: float | None,
    tool_calls: int,
    failed: bool,
) -> None:
    """에이전트 실행 1건의 계측 지표 기록.

    Args:
        step_latencies_ms: 단계별 latency(Slack 수신→컨텍스트 수집→추론→응답).
        tokens: 사용 토큰 수.
        cost_usd: 호출당 비용 USD.
        tool_calls: tool call 횟수.
        failed: 실패 여부(실패율 집계용).
    """
    raise NotImplementedError("Day 8–9: 실행 지표 기록 구현 예정")
