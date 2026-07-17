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
import sys
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

# claude 바이너리 이름(EC2 user-data 가 PATH 에 설치).
CLAUDE_BIN = "claude"

# 모든 headless 호출이 쓸 모델. 미지정 시 CLI 기본값이 바뀌면 결과가 흔들리므로 고정한다.
# ops 가 코드 수정 없이 바꿀 수 있게 SLACKOPS_CLAUDE_MODEL 로 override.
DEFAULT_MODEL = "claude-sonnet-5"
_MODEL_ENV = "SLACKOPS_CLAUDE_MODEL"

DEFAULT_TIMEOUT_S = 770


def _model_args() -> list[str]:
    """`--model <model>` 인자 — 환경변수 override, 없으면 DEFAULT_MODEL."""
    model = os.environ.get(_MODEL_ENV, "").strip() or DEFAULT_MODEL
    return ["--model", model]

# CLI 도구(kubectl/git/aws)가 색상 출력을 켜면 ANSI 이스케이프(CSI)가 결과 텍스트에 섞인다.
# 저장 전 여기서 제거 — web/Slack 등 모든 소비자가 깨끗한 텍스트를 받는다(렌더링은 표시만 담당).
_CSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")

# Claude 프로세스에 전달해도 되는 환경만 명시한다. Slack Socket/App token, dashboard
# secret, AWS credential chain, DynamoDB 연결값은 절대 상속하지 않는다. 내부 SlackOps MCP
# 서버가 필요한 DynamoDB 연결값은 `agent_monitor.mcp_config_json()`의 해당 stdio 서버에만
# 별도로 전달한다. 모델 본체가 IMDS에서 Instance Profile credential을 재획득하지 못하도록
# AWS SDK의 metadata provider도 명시적으로 끈다.
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
        # systemd service egress is localhost-only; Claude and its internal MCP
        # process must therefore inherit the reviewed localhost proxy route.
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "NO_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
        "no_proxy",
    }
)


def _strip_ansi(text: str) -> str:
    """ANSI CSI 이스케이프 시퀀스 제거(색상/커서 등). 일반 텍스트는 그대로."""
    return _CSI_RE.sub("", text)


def _agent_subprocess_env(
    environ: Mapping[str, str] | None = None,
    extra_env: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Claude/MCP 자식 프로세스에 최소 환경만 전달한다.

    Agent가 shell 도구나 취약한 MCP dependency를 통해 환경을 읽더라도 Slack bot/app
    token, OAuth callback secret, AWS credential chain, DynamoDB endpoint를 얻지 못하게
    한다. 내부 MCP 서버의 control-plane 연결은 mcp_config의 per-server env로만 준다.

    Args:
        environ: 원본 환경(테스트 주입점).
        extra_env: 이 실행 1회에만 명시적으로 주입할 값. 상속이 아니라 호출자가 건네야만
            들어온다 — 승인 후 발급된 단기 write credential(write_credentials)과 command
            guard 설정이 이 경로로만 자식에 도달한다.
    """
    source = os.environ if environ is None else environ
    env = {key: value for key in _AGENT_ENV_NAMES if (value := source.get(key))}
    # boto3/AWS CLI 등 표준 SDK가 EC2 metadata endpoint로 instance-profile credential을
    # 다시 찾는 경로를 차단한다. mcp_config의 SlackOps stdio 서버만 이를 false로 override
    # 하며, 그 서버는 allowlisted propose/list control-plane 도구만 노출한다.
    env["AWS_EC2_METADATA_DISABLED"] = "true"
    if extra_env:
        env.update(extra_env)
    return env


def _guard_env(guard_command: str | None) -> dict[str, str]:
    """command guard hook이 필요로 하는 환경(신뢰 명령 이름 + import 경로)."""
    if guard_command is None:
        return {}
    from app.command_guard import GUARD_COMMAND_ENV

    # hook은 claude 프로세스의 자식이므로 이 값은 모델의 Bash subshell이 바꿀 수 없다.
    return {
        GUARD_COMMAND_ENV: guard_command,
        "PYTHONPATH": str(Path(__file__).resolve().parent.parent),
    }


# 실행기 시그니처: (cmd, timeout_s) → (exit_code, stdout, stderr).
# timeout 초과 시 subprocess.TimeoutExpired 를 raise 해야 한다(기본 실행기와 동일 규약).
SubprocessRunner = Callable[[list[str], int], tuple[int, str, str]]


class ClaudeRunnerError(Exception):
    """Claude Code Headless 실행 실패."""


class ClaudeTimeoutError(ClaudeRunnerError):
    """Claude Code Headless 실행이 timeout_s 안에 끝나지 않음."""


@dataclass(frozen=True)
class ToolCall:
    """모델이 실제로 실행한 도구 호출 1건.

    allowlist 는 무엇이 **허용되는지**를 말할 뿐 무엇이 **일어났는지**는 말하지 못한다.
    감사 궤적과 capability 재집계는 이 관측값을 근거로 한다.

    Attributes:
        tool_use_id: Claude 가 부여한 호출 식별자(tool_result 와 짝을 이룬다).
        name: 도구 이름(Bash/Read/Edit/...).
        command: Bash 호출의 명령줄(그 외 도구는 빈 문자열).
        result_hash: 결과 본문의 sha256 — 본문은 감사에 남기지 않는다.
        is_error: 도구가 오류를 돌려줬는지.
    """

    tool_use_id: str
    name: str
    command: str = ""
    result_hash: str = ""
    is_error: bool = False


@dataclass
class RunResult:
    """Claude Code Headless 실행 결과.

    Attributes:
        output: 결과 텍스트(JSON 출력이면 `result` 필드, 아니면 raw stdout/stderr).
        exit_code: subprocess 종료 코드.
        tokens: 사용 토큰 수(input+output, 계측용, 없으면 None).
        cost_usd: 호출 비용 USD(계측용, 없으면 None).
        tool_calls: 이 실행에서 관측된 도구 호출(stream-json 출력에서만 채워진다).
    """

    output: str
    exit_code: int
    tokens: int | None = None
    cost_usd: float | None = None
    tool_calls: tuple[ToolCall, ...] = ()


def guard_hook_argv() -> list[str]:
    """command guard hook을 실행할 argv(현재 인터프리터의 모듈 진입점)."""
    return [sys.executable, "-m", "app.command_guard"]


def build_command(
    prompt: str,
    allowed_tools: list[str],
    mcp_config: str | None = None,
    guard_command: str | None = None,
) -> list[str]:
    """`claude -p` 호출 인자 리스트 생성(shell 미사용 — 인자 주입 불가).

    allowlist 가 비면 `--allowedTools` 자체를 생략한다 — headless 모드는
    승인 프롬프트가 불가능하므로 모든 tool 사용이 거부된다(default deny).

    mcp_config 가 주어지면 `--mcp-config <json|path>` + `--strict-mcp-config`(프로젝트/유저
    .mcp.json 무시, 전달 설정만 사용)를 추가한다 — 에이전트 모니터가 propose_job MCP 서버를
    등록하는 경로. 허용 도구는 `mcp__<server>__<tool>` 형태로 allowed_tools 에 넣는다.

    guard_command 가 주어지면 `--settings` 로 command guard PreToolUse hook 을 설치한다.
    `--allowedTools` 패턴은 명령줄 **앞부분**만 검사하므로(측정: Claude Code 2.1.210 에서
    `Bash(echo:*)` 가 `echo hi; whoami` 를 실행) 그 자체로는 실행 경계가 되지 못한다.
    hook 의 deny 는 allowedTools 허용을 덮어쓰므로, 모든 Bash 호출이 app.command_guard 의
    정규화 + 인자 스키마를 통과해야만 실행된다.

    Args:
        prompt: sanitizer.build_prompt 로 생성된 검증된 프롬프트.
        allowed_tools: 이 명령에 허용된 도구 목록(Tool Allowlist).
        mcp_config: MCP 서버 설정(인라인 JSON 또는 파일 경로). None 이면 미등록(기존 동작).
        guard_command: argv 스키마를 고를 신뢰 명령 이름. None 이면 hook 미설치.
    """
    from app.command_guard import hook_settings_json

    # stream-json 을 쓰는 이유는 스트리밍이 아니라 **관측** 이다: `json` 출력의 result 객체에는
    # tool call 정보가 없어서, 무엇이 실제로 실행됐는지 앱이 알 수 없다(감사 궤적/capability
    # 재집계의 근거가 사라진다). print 모드에서 stream-json 은 --verbose 를 요구한다.
    cmd = [CLAUDE_BIN, "-p", prompt, "--output-format", "stream-json", "--verbose", *_model_args()]
    if guard_command is not None:
        cmd.extend(["--settings", hook_settings_json(guard_hook_argv())])
    if mcp_config:
        cmd.extend(["--mcp-config", mcp_config, "--strict-mcp-config"])
    if allowed_tools:
        cmd.extend(["--allowedTools", *allowed_tools])
    return cmd


def _runner_with_env(extra_env: Mapping[str, str]) -> SubprocessRunner:
    """실 subprocess 실행기 — 이 호출 1회에만 유효한 추가 환경을 주입한다."""

    def run(cmd: list[str], timeout_s: int) -> tuple[int, str, str]:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
            env=_agent_subprocess_env(extra_env=extra_env),
        )
        return proc.returncode, proc.stdout, proc.stderr

    return run


def _default_runner(cmd: list[str], timeout_s: int) -> tuple[int, str, str]:
    """기본 실행기 — 실 subprocess 호출(테스트에서는 사용 금지, mock 주입)."""
    return _runner_with_env({})(cmd, timeout_s)


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


def _tool_calls_from_events(events: list[dict[str, object]]) -> tuple[ToolCall, ...]:
    """관측된 tool_use 를 그 tool_result 와 짝지어 ToolCall 로 만든다."""
    from app.store import result_digest

    uses: dict[str, tuple[str, str]] = {}
    order: list[str] = []
    results: dict[str, tuple[str, bool]] = {}
    for event in events:
        message = event.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use" and isinstance(block.get("id"), str):
                raw_input = block.get("input")
                command = ""
                if isinstance(raw_input, dict) and isinstance(raw_input.get("command"), str):
                    command = raw_input["command"]
                uses[block["id"]] = (str(block.get("name", "")), command)
                order.append(block["id"])
            elif block.get("type") == "tool_result" and isinstance(
                block.get("tool_use_id"), str
            ):
                results[block["tool_use_id"]] = (
                    str(block.get("content", "")),
                    bool(block.get("is_error", False)),
                )
    calls: list[ToolCall] = []
    for use_id in order:
        name, command = uses[use_id]
        body, is_error = results.get(use_id, ("", False))
        calls.append(
            ToolCall(
                tool_use_id=use_id,
                name=name,
                command=command,
                result_hash=result_digest(body) if body else "",
                is_error=is_error,
            )
        )
    return tuple(calls)


def _parse_result(exit_code: int, stdout: str, stderr: str) -> RunResult:
    """stdout 을 RunResult 로 파싱.

    stream-json(JSONL)과 단일 JSON 객체를 모두 받는다. 단일 객체 경로는 `--output-format
    json` 을 쓰던 시절의 출력 모양이며, 실행기를 주입하는 테스트가 그 모양을 그대로 쓴다 —
    파서가 한쪽만 알면 mock 과 실물이 갈라진다.
    """
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
    events: list[dict[str, object]] = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(event, dict):
            events.append(event)
    if events:
        final = next(
            (e for e in reversed(events) if e.get("type") == "result"), None
        )
        output = ""
        tokens: int | None = None
        cost: float | None = None
        if final is not None:
            text = final.get("result")
            output = text if isinstance(text, str) else ""
            tokens = _parse_tokens(final)
            cost = _parse_cost(final)
        return RunResult(
            output=_strip_ansi(output),
            exit_code=exit_code,
            tokens=tokens,
            cost_usd=cost,
            tool_calls=_tool_calls_from_events(events),
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
    cmd = [CLAUDE_BIN, "-p", prompt, "--output-format", "stream-json", "--verbose", *_model_args()]
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
    guard_command: str | None = None,
    extra_env: Mapping[str, str] | None = None,
) -> RunResult:
    """Claude Code Headless 를 subprocess 로 실행.

    Args:
        prompt: sanitizer.build_prompt 로 생성된 검증된 프롬프트.
        allowed_tools: 이 명령에 허용된 도구 목록(Tool Allowlist).
        timeout_s: 실행 타임아웃(초).
        runner: subprocess 실행기(테스트 주입점). None 이면 실 subprocess.
        mcp_config: MCP 서버 설정(인라인 JSON/경로). 주어지면 --mcp-config + --strict-mcp-config.
        guard_command: command guard PreToolUse hook 에 적용할 신뢰 명령 이름.
        extra_env: 이 실행 1회에만 주입할 환경(승인 후 발급된 단기 write credential).
            상속이 아니라 명시 전달이므로 prepare/진단 경로에는 절대 존재하지 않는다.

    Returns:
        RunResult — 출력 + 계측 메타. 실패는 raise 하지 않고 exit_code 로 전달.

    Raises:
        ClaudeTimeoutError: timeout_s 초과.
    """
    call_env = {**_guard_env(guard_command), **(extra_env or {})}
    active_runner: SubprocessRunner = (
        runner if runner is not None else _runner_with_env(call_env)
    )
    cmd = build_command(prompt, allowed_tools, mcp_config, guard_command)
    try:
        exit_code, stdout, stderr = active_runner(cmd, timeout_s)
    except subprocess.TimeoutExpired as exc:
        raise ClaudeTimeoutError(
            f"claude headless timed out after {timeout_s}s"
        ) from exc
    return _parse_result(exit_code, stdout, stderr)
