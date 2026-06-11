"""`/devops ping` — 헬스체크.

가장 단순한 명령. Socket Mode 연결·라우팅·응답 경로가 살아있는지 확인. 권한 Level 0.
"""

from __future__ import annotations


def handle_ping() -> str:
    """헬스체크 응답 문자열 반환.

    Returns:
        Slack 에 게시할 헬스 상태 메시지.
    """
    raise NotImplementedError("Day 1–3: ping 핸들러 구현 예정")
