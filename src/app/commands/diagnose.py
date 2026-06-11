"""`/devops diagnose <service>` — CloudWatch + kubectl + git diff 종합 진단.

여러 untrusted 소스(로그/describe/diff)를 sanitizer 로 격리해 Claude 종합 진단에 전달. 권한 Level 0.
"""

from __future__ import annotations


def handle_diagnose(service: str) -> str:
    """서비스 상태를 CloudWatch·kubectl·git diff 로 종합 진단.

    Args:
        service: 대상 서비스 이름(검증된 값).

    Returns:
        Slack 에 게시할 진단 결과.
    """
    raise NotImplementedError("Day 4–5: diagnose 핸들러(다중 소스 + Sanitizer + 진단) 구현 예정")
