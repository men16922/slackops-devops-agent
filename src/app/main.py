"""FastAPI 진입(health/metrics) + Socket Mode 부트스트랩.

EC2 상주 단일 서비스의 진입점. FastAPI 는 health/metrics 노출 전용이며
인바운드 명령 경로가 아니다(Slack 은 Socket Mode 아웃바운드) — **127.0.0.1 바인딩 고정.**
fastapi/uvicorn/structlog 은 lazy import — 미설치 환경에서도 모듈 import 가능.
"""

from __future__ import annotations

import threading
from typing import Any

from app import __version__

# health/metrics 는 로컬 진단 전용 — 외부 노출 금지(인바운드 포트 없음 불변).
HEALTH_HOST = "127.0.0.1"
HEALTH_PORT = 8080


def create_app() -> Any:
    """FastAPI 앱 생성 — `/health`, `/metrics` 라우트 등록.

    Returns:
        FastAPI 인스턴스.
    """
    from fastapi import FastAPI  # lazy: 미설치 환경 import-safe

    api = FastAPI(title="slackops-devops-agent", version=__version__)

    @api.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    @api.get("/metrics")
    def metrics() -> dict[str, str]:
        # 지표 수집은 TelemetryStore(+선택 OTel span emit)가 담당 — 대시보드는 store
        # 피드를 읽는다. 이 endpoint 는 liveness 확인용 placeholder 로 유지.
        return {"status": "ok", "note": "metrics are collected in TelemetryStore/OTel"}

    return api


def bootstrap_socket_mode() -> None:
    """Slack Bolt Socket Mode client 부트스트랩 + 기본 명령 등록 + 연결 시작(블로킹).

    인바운드 포트 없이 아웃바운드 WebSocket 으로 Slack 이벤트 수신.
    """
    from app.slack_handler import SlackHandler, register_default_commands

    handler = register_default_commands(SlackHandler.from_env())
    _serve_proposal_notifier(handler)
    handler.start()


def _serve_proposal_notifier(handler: Any) -> None:
    """새 AGENT 제안을 Slack 채널로 알리는 폴링 루프를 데몬 스레드에서 기동.

    SLACK_NOTIFY_CHANNEL 미설정 시 no-op(기능 비활성). Slack 앱 프로세스가 이미 보유한
    Bolt client(봇 토큰)로 게시한다 — 별도 프로세스/유닛·토큰 배선 불필요. 스레드 최상위
    try/except 로 알림 실패가 Slack 앱을 죽이지 않게 한다(health 스레드 선례).
    """
    import os

    channel = os.environ.get("SLACK_NOTIFY_CHANNEL")
    if not channel:
        return

    import structlog

    from app.mcp_server import store_from_env
    from app.proposal_notifier import make_post_fn, run_forever

    log = structlog.get_logger()

    def _loop() -> None:
        try:
            store = store_from_env()
            post_fn = make_post_fn(handler.app.client, channel)
            run_forever(store, post_fn)
        except Exception as exc:  # noqa: BLE001 — 알림 스레드는 Slack 앱을 죽이면 안 된다.
            log.warning("proposal_notifier.crashed", error=str(exc))

    threading.Thread(target=_loop, daemon=True, name="proposal-notifier").start()


def _serve_health_api() -> None:
    """health/metrics FastAPI 를 데몬 스레드에서 기동(127.0.0.1 전용)."""
    import uvicorn  # lazy

    threading.Thread(
        target=uvicorn.run,
        args=(create_app(),),
        kwargs={"host": HEALTH_HOST, "port": HEALTH_PORT, "log_level": "warning"},
        daemon=True,
        name="health-api",
    ).start()


def main() -> None:
    """프로세스 진입점 — logging → health API(스레드) → Socket Mode(블로킹)."""
    import structlog  # lazy

    log = structlog.get_logger()
    log.info("starting", service="slackops-devops-agent", version=__version__)
    _serve_health_api()
    bootstrap_socket_mode()


if __name__ == "__main__":
    main()
