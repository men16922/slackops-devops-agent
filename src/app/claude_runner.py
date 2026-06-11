"""Claude Code Headless subprocess wrapper.

Claude Code 를 Headless(subprocess) 로 호출한다. **직접 모델 SDK 래퍼(Bedrock/OpenAI) 생성 금지.**
명령별 Tool Allowlist(주입 방어 2계층)를 permissions 설정으로 강제한다.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RunResult:
    """Claude Code Headless 실행 결과.

    Attributes:
        output: stdout 결과 텍스트.
        exit_code: subprocess 종료 코드.
        tokens: 사용 토큰 수(계측용, 없으면 None).
        cost_usd: 호출 비용 USD(계측용, 없으면 None).
        tool_calls: tool call 횟수(계측용).
    """

    output: str
    exit_code: int
    tokens: int | None = None
    cost_usd: float | None = None
    tool_calls: int = 0


def run_headless(prompt: str, allowed_tools: list[str], timeout_s: int = 300) -> RunResult:
    """Claude Code Headless 를 subprocess 로 실행.

    Args:
        prompt: sanitizer.build_prompt 로 생성된 검증된 프롬프트.
        allowed_tools: 이 명령에 허용된 도구 목록(Tool Allowlist).
        timeout_s: 실행 타임아웃(초).

    Returns:
        RunResult — 출력 + 계측 메타.
    """
    raise NotImplementedError("Day 1–3: Claude Code Headless subprocess 호출 구현 예정")
