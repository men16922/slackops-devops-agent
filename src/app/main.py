"""FastAPI 진입(health/metrics) + Socket Mode 부트스트랩.

EC2 상주 단일 서비스의 진입점. FastAPI 는 health/metrics 노출 전용이며
인바운드 명령 경로가 아니다(Slack 은 Socket Mode 아웃바운드). 로직은 Day 1–3 트랙에서 구현.
"""

from __future__ import annotations

from typing import Any


def create_app() -> Any:
    """FastAPI 앱 생성 — `/health`, `/metrics` 라우트 등록.

    Returns:
        FastAPI 인스턴스 (stub: 미구현).
    """
    raise NotImplementedError("Day 1–3: FastAPI app(health/metrics) 구현 예정")


def bootstrap_socket_mode() -> None:
    """Slack Bolt Socket Mode client 부트스트랩 + slack_handler 연결.

    인바운드 포트 없이 아웃바운드 WebSocket 으로 Slack 이벤트 수신.
    """
    raise NotImplementedError("Day 1–3: Socket Mode 부트스트랩 구현 예정")


def main() -> None:
    """프로세스 진입점 — telemetry 셋업 → app → Socket Mode 기동."""
    raise NotImplementedError("Day 1–3: 진입점 구현 예정")


if __name__ == "__main__":
    main()
