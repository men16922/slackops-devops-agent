"""명령 핸들러 공유 Slack 응답 문자열 빌더.

logs/diagnose(및 향후 tf-review/pr)가 같은 입력/실행 오류 메시지를 복붙하지 않도록
한 곳에 모은다. 명령별로 다른 부분은 인자(usage_hint, what)로만 변형한다.
"""

from __future__ import annotations


def invalid_service_reply(usage_hint: str) -> str:
    """service 인자 검증 실패 응답.

    Args:
        usage_hint: 명령별 사용법 한 줄(예: ``사용법: `/devops logs <service>` ``).
    """
    return (
        ":no_entry: 서비스 이름이 올바르지 않습니다 — "
        "허용 문자: 영숫자와 `_ . / # -` (맨 앞 `-` 불가). " + usage_hint
    )


def no_data_reply(service: str, what: str) -> str:
    """수집 결과가 비어 Claude 호출을 건너뛴 응답.

    Args:
        service: 검증된 서비스 이름.
        what: 무엇을 못 찾았는지(예: "최근 로그 이벤트를").
    """
    return f":mag: `{service}` 에서 {what} 찾지 못했습니다."


def exec_failed_reply(service: str, what: str, exit_code: int, output: str) -> str:
    """Claude 실행이 비정상 종료(exit != 0)한 응답.

    Args:
        service: 검증된 서비스 이름.
        what: 실행 종류(예: "로그 분석", "진단").
        exit_code: claude headless 종료 코드.
        output: claude 출력(또는 stderr).
    """
    return f":warning: `{service}` {what} 실행이 실패했습니다 (exit {exit_code}).\n{output}"
