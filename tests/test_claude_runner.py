"""claude_runner 테스트 — mock 실행기 주입(실 `claude` 호출 없음)."""

from __future__ import annotations

import json
import subprocess

import pytest

from app.claude_runner import (
    CLAUDE_BIN,
    ClaudeRunnerError,
    ClaudeTimeoutError,
    RunResult,
    build_command,
    run_headless,
)


def _result_json(
    result: str = "analysis done",
    tokens: tuple[int, int] = (1200, 340),
    cost: float = 0.0123,
) -> str:
    return json.dumps(
        {
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "result": result,
            "total_cost_usd": cost,
            "usage": {"input_tokens": tokens[0], "output_tokens": tokens[1]},
        }
    )


class RecordingRunner:
    """주입용 mock 실행기 — 호출 인자를 기록하고 고정 응답 반환."""

    def __init__(self, exit_code: int = 0, stdout: str = "", stderr: str = "") -> None:
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr
        self.calls: list[tuple[list[str], int]] = []

    def __call__(self, cmd: list[str], timeout_s: int) -> tuple[int, str, str]:
        self.calls.append((cmd, timeout_s))
        return self.exit_code, self.stdout, self.stderr


# ── build_command ────────────────────────────────────────────────


def test_build_command_basic_shape() -> None:
    cmd = build_command("do analysis", ["Bash(aws logs:*)", "Read"])
    assert cmd[0] == CLAUDE_BIN
    assert cmd[1:3] == ["-p", "do analysis"]
    assert "--output-format" in cmd
    assert cmd[cmd.index("--output-format") + 1] == "json"
    idx = cmd.index("--allowedTools")
    assert cmd[idx + 1 :] == ["Bash(aws logs:*)", "Read"]


def test_build_command_empty_allowlist_omits_flag() -> None:
    """allowlist 가 비면 flag 생략 — headless 는 승인 불가라 전체 tool 거부(default deny)."""
    cmd = build_command("p", [])
    assert "--allowedTools" not in cmd


def test_build_command_is_arg_list_no_shell() -> None:
    """shell 문자열이 아닌 인자 리스트 — 프롬프트 내 메타문자가 해석되지 않는다."""
    cmd = build_command("x; rm -rf / && echo $(pwd)", ["Read"])
    assert isinstance(cmd, list)
    assert "x; rm -rf / && echo $(pwd)" in cmd


# ── run_headless 성공 ────────────────────────────────────────────


def test_success_parses_json_output() -> None:
    runner = RecordingRunner(stdout=_result_json())
    result = run_headless("prompt", ["Read"], runner=runner)
    assert result == RunResult(
        output="analysis done", exit_code=0, tokens=1540, cost_usd=0.0123
    )


def test_runner_receives_command_and_timeout() -> None:
    runner = RecordingRunner(stdout=_result_json())
    run_headless("prompt", ["Bash(kubectl get:*)"], timeout_s=42, runner=runner)
    assert len(runner.calls) == 1
    cmd, timeout_s = runner.calls[0]
    assert timeout_s == 42
    assert cmd == build_command("prompt", ["Bash(kubectl get:*)"])


def test_non_json_stdout_falls_back_to_raw_text() -> None:
    runner = RecordingRunner(stdout="plain text answer")
    result = run_headless("p", [], runner=runner)
    assert result.output == "plain text answer"
    assert result.exit_code == 0
    assert result.tokens is None
    assert result.cost_usd is None


def test_json_missing_metrics_yields_none() -> None:
    runner = RecordingRunner(stdout=json.dumps({"result": "ok"}))
    result = run_headless("p", [], runner=runner)
    assert result.output == "ok"
    assert result.tokens is None
    assert result.cost_usd is None


def test_json_partial_usage_yields_none_tokens() -> None:
    runner = RecordingRunner(
        stdout=json.dumps({"result": "ok", "usage": {"input_tokens": 10}})
    )
    result = run_headless("p", [], runner=runner)
    assert result.tokens is None


def test_json_non_numeric_cost_yields_none() -> None:
    runner = RecordingRunner(
        stdout=json.dumps({"result": "ok", "total_cost_usd": "free"})
    )
    result = run_headless("p", [], runner=runner)
    assert result.cost_usd is None


def test_json_without_result_field_keeps_raw_stdout() -> None:
    raw = json.dumps({"type": "result", "is_error": True})
    runner = RecordingRunner(stdout=raw)
    result = run_headless("p", [], runner=runner)
    assert result.output == raw


# ── run_headless 실패 ────────────────────────────────────────────


def test_failure_returns_exit_code_with_stderr() -> None:
    """실패는 raise 가 아니라 exit_code 로 전달 — stdout 이 비면 stderr 를 출력으로."""
    runner = RecordingRunner(exit_code=1, stdout="", stderr="auth error")
    result = run_headless("p", ["Read"], runner=runner)
    assert result.exit_code == 1
    assert result.output == "auth error"


def test_failure_with_stdout_prefers_stdout() -> None:
    runner = RecordingRunner(exit_code=2, stdout="partial output", stderr="boom")
    result = run_headless("p", [], runner=runner)
    assert result.exit_code == 2
    assert result.output == "partial output"


# ── timeout ──────────────────────────────────────────────────────


def test_timeout_raises_claude_timeout_error() -> None:
    def timing_out(cmd: list[str], timeout_s: int) -> tuple[int, str, str]:
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=timeout_s)

    with pytest.raises(ClaudeTimeoutError) as excinfo:
        run_headless("p", ["Read"], timeout_s=7, runner=timing_out)
    assert "7" in str(excinfo.value)


def test_timeout_error_is_runner_error_subclass() -> None:
    assert issubclass(ClaudeTimeoutError, ClaudeRunnerError)
