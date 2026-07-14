"""Claude Code Headless subprocess wrapper.

Claude Code 를 Headless(subprocess) 로 호출한다. **직접 모델 SDK 래퍼(Bedrock/OpenAI) 생성 금지.**
명령별 Tool Allowlist(주입 방어 2계층)를 `--allowedTools` 로 강제한다.

subprocess 실행기는 주입 가능(`runner` 인자) — 단위 테스트는 mock 을 주입하고
실 `claude` 바이너리는 호출하지 않는다. shell=False(인자 리스트) 고정.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from typing import Callable

# claude 바이너리 이름(EC2 user-data 가 PATH 에 설치).
CLAUDE_BIN = "claude"

DEFAULT_TIMEOUT_S = 300

# CLI 도구(kubectl/git/aws)가 색상 출력을 켜면 ANSI 이스케이프(CSI)가 결과 텍스트에 섞인다.
# 저장 전 여기서 제거 — web/Slack 등 모든 소비자가 깨끗한 텍스트를 받는다(렌더링은 표시만 담당).
_CSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")

# Claude와 Claude가 기동하는 MCP subprocess에 전달해도 되는 환경만 명시한다. Slack
# Socket/App token, dashboard secret 등 서비스 자체에만 필요한 값은 절대 상속하지 않는다.
# AWS credential 값은 로컬 개발 경로를 위해서만 허용하며, EC2에서는 비어 있어 Instance
# Profile을 기본 credential chain으로 사용한다.
_AGENT_ENV_NAMES: frozenset[str] = frozenset(
    {
        "PATH",
        "HOME",
        "LANG",
        "LC_ALL",
        "TZ",
        "TMPDIR",
        "TMP",
        "TEMP",
        "XDG_CACHE_HOME",
        "XDG_CONFIG_HOME",
        "UV_CACHE_DIR",
        "CLAUDE_CODE_OAUTH_TOKEN",
        "AWS_REGION",
        "AWS_DEFAULT_REGION",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "AWS_PROFILE",
        "AWS_EC2_METADATA_SERVICE_ENDPOINT",
        "DDB_ENDPOINT",
        "DDB_TABLE",
    }
)


def _strip_ansi(text: str) -> str:
    """ANSI CSI 이스케이프 시퀀스 제거(색상/커서 등). 일반 텍스트는 그대로."""
    return _CSI_RE.sub("", text)


def _agent_subprocess_env(environ: Mapping[str, str] | None = None) -> dict[str, str]:
    """Claude/MCP 자식 프로세스에 최소 환경만 전달한다.

    Agent가 shell 도구나 취약한 MCP dependency를 통해 환경을 읽더라도 Slack bot/app
    token, OAuth callback secret 등 control-plane 비밀을 얻지 못하게 한다. 인증에 필요한
    Claude OAuth와 AWS credential chain 관련 값만 명시적으로 전달한다.
    """
    source = os.environ if environ is None else environ
    return {key: value for key in _AGENT_ENV_NAMES if (value := source.get(key))}


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
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout_s,
        check=False,
        env=_agent_subprocess_env(),
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
        output = result_text if isinstance(result_text, str) else stdout
        return RunResult(
            output=_strip_ansi(output),
            exit_code=exit_code,
            tokens=_parse_tokens(payload),
            cost_usd=_parse_cost(payload),
        )
    output = stdout if stdout.strip() else stderr
    return RunResult(output=_strip_ansi(output), exit_code=exit_code)


# ── 스트리밍(대화 producer 용) ─────────────────────────────────────────────
# 스트리밍 실행기: (cmd, timeout_s) → stdout 줄(JSONL) 이터레이터. 줄이 도착하는 대로 yield.
StreamRunner = Callable[[list[str], int], Iterator[str]]

# tool_result 본문에서 propose_job 이 돌려준 job_id 추출용(MCP 결과 = {"ok":true,"job_id":...}).
_JOB_ID_RE = re.compile(r'"job_id"\s*:\s*"([^"]+)"')


@dataclass
class StreamResult:
    """스트리밍 실행 1회의 누적 결과.

    Attributes:
        output: 누적된 assistant 텍스트.
        tokens / cost_usd: 최종 result 이벤트의 계측(없으면 None).
        proposed_job_id: 대화 중 propose_job MCP 가 적재한 job id(없으면 None).
        tool_uses: 호출된 도구 이름 목록(계측/디버그).
    """

    output: str = ""
    tokens: int | None = None
    cost_usd: float | None = None
    proposed_job_id: str | None = None
    tool_uses: list[str] = field(default_factory=list)


def build_stream_command(
    prompt: str,
    allowed_tools: list[str],
    mcp_config: str | None = None,
) -> list[str]:
    """`claude -p --output-format stream-json` 인자 리스트(JSONL 스트리밍)."""
    cmd = [CLAUDE_BIN, "-p", prompt, "--output-format", "stream-json", "--verbose"]
    if mcp_config:
        cmd.extend(["--mcp-config", mcp_config, "--strict-mcp-config"])
    if allowed_tools:
        cmd.extend(["--allowedTools", *allowed_tools])
    return cmd


def _default_stream_runner(cmd: list[str], timeout_s: int) -> Iterator[str]:
    """기본 스트리밍 실행기 — Popen 으로 stdout 을 줄단위로 흘린다(테스트는 mock 주입)."""
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        env=_agent_subprocess_env(),
    )
    assert proc.stdout is not None
    try:
        yield from proc.stdout
    finally:
        proc.stdout.close()
        try:
            proc.wait(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            proc.kill()
            raise ClaudeTimeoutError(f"claude stream timed out after {timeout_s}s")


def _scan_job_id(value: object) -> str | None:
    """파싱된 이벤트(중첩 dict/list)의 문자열 값에서 propose_job job_id 추출(없으면 None).

    tool_result content 가 JSON 문자열로 박혀 와도(이중 이스케이프) 파싱된 str 값에는
    실제 따옴표가 있으므로 그 위에서 매칭한다.
    """
    if isinstance(value, str):
        match = _JOB_ID_RE.search(value)
        return match.group(1) if match else None
    if isinstance(value, dict):
        for sub in value.values():
            found = _scan_job_id(sub)
            if found:
                return found
    elif isinstance(value, list):
        for sub in value:
            found = _scan_job_id(sub)
            if found:
                return found
    return None


def _handle_stream_event(
    event: dict[str, object],
    on_chunk: Callable[[str], None],
    result: StreamResult,
    parts: list[str],
) -> None:
    """stream-json 이벤트 1건을 해석해 청크 콜백 + result 누적(버전 차 방어적 파싱)."""
    etype = event.get("type")
    # 부분 델타(--include-partial-messages 지원 버전).
    if etype in ("content_block_delta", "stream_event"):
        delta = event.get("delta")
        if isinstance(delta, dict) and isinstance(delta.get("text"), str):
            text = _strip_ansi(delta["text"])
            parts.append(text)
            on_chunk(text)
        return
    # 메시지 단위(assistant 턴) — text 블록은 청크로, tool_use 는 기록.
    if etype == "assistant":
        message = event.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "text" and isinstance(block.get("text"), str):
                    text = _strip_ansi(block["text"])
                    parts.append(text)
                    on_chunk(text)
                elif block.get("type") == "tool_use" and isinstance(
                    block.get("name"), str
                ):
                    result.tool_uses.append(block["name"])
        return
    # tool_result(user 이벤트) — propose_job 결과의 job_id 추출.
    if etype == "user" and result.proposed_job_id is None:
        result.proposed_job_id = _scan_job_id(event)
        return
    # 최종 result — 계측.
    if etype == "result":
        result.tokens = _parse_tokens(event)
        result.cost_usd = _parse_cost(event)
        final_text = event.get("result")
        if not parts and isinstance(final_text, str):
            parts.append(_strip_ansi(final_text))
        if result.proposed_job_id is None:
            result.proposed_job_id = _scan_job_id(event)


def run_headless_stream(
    prompt: str,
    allowed_tools: list[str],
    *,
    on_chunk: Callable[[str], None],
    timeout_s: int = DEFAULT_TIMEOUT_S,
    runner: StreamRunner | None = None,
    mcp_config: str | None = None,
) -> StreamResult:
    """Claude Code Headless 를 스트리밍 실행 — 텍스트 청크를 on_chunk 로 흘린다.

    JSONL 이벤트를 줄단위로 파싱해 assistant 텍스트는 on_chunk 콜백으로, 최종 result 의
    tokens/cost, propose_job 이 적재한 job_id 를 StreamResult 로 모은다. on_chunk 예외는
    호출자(에이전트)가 책임진다.

    Args:
        prompt: sanitizer.build_prompt 로 생성된 검증 프롬프트.
        allowed_tools: Tool Allowlist(대화 producer 는 propose_job 만).
        on_chunk: 텍스트 델타 1건마다 호출(예: 대화 store 에 청크 append).
        runner: 스트리밍 실행기(테스트 주입). None 이면 실 Popen.
        mcp_config: propose_job MCP 등록(인라인 JSON/경로).
    """
    active: StreamRunner = runner if runner is not None else _default_stream_runner
    cmd = build_stream_command(prompt, allowed_tools, mcp_config)
    result = StreamResult()
    parts: list[str] = []
    for line in active(cmd, timeout_s):
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(event, dict):
            _handle_stream_event(event, on_chunk, result, parts)
    result.output = "".join(parts)
    return result


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
