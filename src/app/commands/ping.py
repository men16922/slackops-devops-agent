"""`/devops ping` — 헬스체크.

가장 단순한 명령. Socket Mode 연결·라우팅·응답 경로가 살아있는지 확인. 권한 Level 0.
Claude 호출 없음 — 순수 로컬 상태 응답.
"""

from __future__ import annotations

import platform
import socket

from app import __version__


def handle_ping() -> str:
    """헬스체크 응답 문자열 반환.

    Returns:
        Slack 에 게시할 헬스 상태 메시지(버전/호스트/런타임).
    """
    return (
        ":white_check_mark: pong — slackops-devops-agent "
        f"v{__version__} on `{socket.gethostname()}` "
        f"(python {platform.python_version()})"
    )
