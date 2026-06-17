"""Claude Code Headless subprocess wrapper.

Claude Code 를 Headless(subprocess) 로 호출한다. **직접 모델 SDK 래퍼(Bedrock/OpenAI) 생성 금지.**
명령별 Tool Allowlist(주입 방어 2계층)를 `--allowedTools` 로 강제한다.

subprocess 실행기는 주입 가능(`runner` 인자) — 단위 테스트는 mock 을 주입하고
실 `claude` 바이너리는 호출하지 않는다. shell=False(인자 리스트) 고정.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from typing import Callable

# claude 바이너리 이름(EC2 user-data 가 PATH 에 설치).
CLAUDE_BIN = "claude"

DEFAULT_TIMEOUT_S = 300

# 실행기 시그니처: (cmd, timeout_s) → (exit_code, stdout, stderr).
# timeout 초과 시 subprocess.TimeoutExpired 를 raise 해야 한다(기본 실행기와 동일 규약).
SubprocessRunner = Callable[[list[str], int], tuple[int, str, str]]


class ClaudeRunnerError(Exception):
    """Claude Code Headless 실행 실패."""


class ClaudeTimeoutError(ClaudeRunnerError):
    """Claude Code Headless 실행이 timeout_s 안에 끝나지 않음."""


@dataclass
class RunResult:
    """Claude Code Headless 실행 결과.

    tool call 횟수는 `--output-format json` 의 result 객체에 없어 여기서 제공하지 않는다.
    계측이 필요하면 stream-json 파싱이 도입될 때 추가한다(telemetry.record_run_metrics 는
    tool_calls 를 별도 인자로 받는다).

    Attributes:
        output: 결과 텍스트(JSON 출력이면 `result` 필드, 아니면 raw stdout/stderr).
        exit_code: subprocess 종료 코드.
        tokens: 사용 토큰 수(input+output, 계측용, 없으면 None).
        cost_usd: 호출 비용 USD(계측용, 없으면 None).
    """

    output: str
    exit_code: int
    tokens: int | None = None
    cost_usd: float | None = None


def build_command(
    prompt: str,
    allowed_tools: list[str],
    mcp_config: str | None = None,
) -> list[str]:
    """`claude -p` 호출 인자 리스트 생성(shell 미사용 — 인자 주입 불가).

    allowlist 가 비면 `--allowedTools` 자체를 생략한다 — headless 모드는
    승인 프롬프트가 불가능하므로 모든 tool 사용이 거부된다(default deny).

    mcp_config 가 주어지면 `--mcp-config <json|path>` + `--strict-mcp-config`(프로젝트/유저
    .mcp.json 무시, 전달 설정만 사용)를 추가한다 — 에이전트 모니터가 propose_job MCP 서버를
    등록하는 경로. 허용 도구는 `mcp__<server>__<tool>` 형태로 allowed_tools 에 넣는다.

    Args:
        prompt: sanitizer.build_prompt 로 생성된 검증된 프롬프트.
        allowed_tools: 이 명령에 허용된 도구 목록(Tool Allowlist).
        mcp_config: MCP 서버 설정(인라인 JSON 또는 파일 경로). None 이면 미등록(기존 동작).
    """
    cmd = [CLAUDE_BIN, "-p", prompt, "--output-format", "json"]
    if mcp_config:
        cmd.extend(["--mcp-config", mcp_config, "--strict-mcp-config"])
    if allowed_tools:
        cmd.extend(["--allowedTools", *allowed_tools])
    return cmd


def _default_runner(cmd: list[str], timeout_s: int) -> tuple[int, str, str]:
    """기본 실행기 — 실 subprocess 호출(테스트에서는 사용 금지, mock 주입)."""
    proc = subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout_s, check=False
    )
    return proc.returncode, proc.stdout, proc.stderr


def _parse_tokens(payload: dict[str, object]) -> int | None:
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        return None
    input_tokens = usage.get("input_tokens")
    output_tokens = usage.get("output_tokens")
    if isinstance(input_tokens, int) and isinstance(output_tokens, int):
        return input_tokens + output_tokens
    return None


def _parse_cost(payload: dict[str, object]) -> float | None:
    cost = payload.get("total_cost_usd")
    if isinstance(cost, (int, float)) and not isinstance(cost, bool):
        return float(cost)
    return None


def _parse_result(exit_code: int, stdout: str, stderr: str) -> RunResult:
    """stdout 을 RunResult 로 파싱 — `--output-format json` 우선, 실패 시 raw 텍스트."""
    try:
        payload = json.loads(stdout)
    except (json.JSONDecodeError, ValueError):
        payload = None
    if isinstance(payload, dict):
        result_text = payload.get("result")
        return RunResult(
            output=result_text if isinstance(result_text, str) else stdout,
            exit_code=exit_code,
            tokens=_parse_tokens(payload),
            cost_usd=_parse_cost(payload),
        )
    output = stdout if stdout.strip() else stderr
    return RunResult(output=output, exit_code=exit_code)


def run_headless(
    prompt: str,
    allowed_tools: list[str],
    timeout_s: int = DEFAULT_TIMEOUT_S,
    runner: SubprocessRunner | None = None,
    mcp_config: str | None = None,
) -> RunResult:
    """Claude Code Headless 를 subprocess 로 실행.

    Args:
        prompt: sanitizer.build_prompt 로 생성된 검증된 프롬프트.
        allowed_tools: 이 명령에 허용된 도구 목록(Tool Allowlist).
        timeout_s: 실행 타임아웃(초).
        runner: subprocess 실행기(테스트 주입점). None 이면 실 subprocess.
        mcp_config: MCP 서버 설정(인라인 JSON/경로). 주어지면 --mcp-config + --strict-mcp-config.

    Returns:
        RunResult — 출력 + 계측 메타. 실패는 raise 하지 않고 exit_code 로 전달.

    Raises:
        ClaudeTimeoutError: timeout_s 초과.
    """
    active_runner: SubprocessRunner = runner if runner is not None else _default_runner
    cmd = build_command(prompt, allowed_tools, mcp_config)
    try:
        exit_code, stdout, stderr = active_runner(cmd, timeout_s)
    except subprocess.TimeoutExpired as exc:
        raise ClaudeTimeoutError(
            f"claude headless timed out after {timeout_s}s"
        ) from exc
    return _parse_result(exit_code, stdout, stderr)
