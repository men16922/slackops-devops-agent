"""`/devops logs <service>` — CloudWatch 조회 + 분석.

CloudWatch Logs 를 조회해 untrusted 로그를 sanitizer 로 격리한 뒤 Claude 분석에 전달. 권한 Level 0.
Tool Allowlist: `aws logs` 만.
"""

from __future__ import annotations


def handle_logs(service: str) -> str:
    """서비스의 CloudWatch 로그를 조회·분석해 요약 반환.

    Args:
        service: 대상 서비스 이름(검증된 값).

    Returns:
        Slack 에 게시할 분석 요약.
    """
    raise NotImplementedError("Day 4–5: logs 핸들러(CloudWatch 조회 + Sanitizer + 분석) 구현 예정")
