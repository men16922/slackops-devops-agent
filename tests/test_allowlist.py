"""allowlist 테스트 — 명령별 매핑 + default deny + 금지 불변 검증 + claude_runner 연결."""

from __future__ import annotations

import re
import subprocess

import pytest

from app.allowlist import (
    AllowlistDenied,
    allowed_tools,
    known_commands,
    run_for_command,
    validate_mapping,
)
from app.claude_runner import ClaudeTimeoutError, build_command
from app.permissions import FORBIDDEN_ACTIONS, PermissionDenied
from app.telemetry import RunMetrics
from tests._helpers import RecordingRunner, result_json as _result_json


# ── 명령별 매핑 ──────────────────────────────────────────────────


def test_observation_commands_have_no_model_tools() -> None:
    """AWS/kubectl/git data는 앱 adapter가 수집하므로 Claude는 분석만 한다."""
    assert allowed_tools("logs") == []
    assert allowed_tools("diagnose") == []
    assert allowed_tools("detect") == []


def test_tf_review_has_plan_but_no_apply_path() -> None:
    tools = allowed_tools("tf-review")
    assert any("terraform plan" in t for t in tools)
    assert not any("apply" in t.lower() for t in tools)


def test_pr_allowlist_covers_branch_to_pr_workflow() -> None:
    tools = allowed_tools("pr")
    assert "Bash(git commit:*)" in tools
    assert "Bash(gh pr create:*)" in tools
    assert not any("merge" in t.lower() for t in tools)


def test_known_commands_are_claude_backed_only() -> None:
    assert known_commands() == frozenset(
        {"logs", "diagnose", "detect", "tf-review", "pr"}
    )


def test_allowlist_matches_permissions_registry() -> None:
    """allowlist 명령 집합 == permissions 의 claude_backed 집합(finding #7 드리프트 차단).

    import 시 _cross_check_with_permissions 가 이미 강제하지만, 회귀 가드로 명시한다.
    """
    from app import permissions

    assert known_commands() == permissions.claude_backed_commands()


# ── default deny ─────────────────────────────────────────────────


def test_unknown_command_default_deny() -> None:
    with pytest.raises(AllowlistDenied):
        allowed_tools("destroy-everything")


def test_ping_not_in_allowlist() -> None:
    """ping 은 Claude 를 경유하지 않으므로 allowlist 에 없다(default deny)."""
    with pytest.raises(AllowlistDenied):
        allowed_tools("ping")


def test_allowed_tools_returns_copy() -> None:
    first = allowed_tools("logs")
    first.append("Bash(rm:*)")
    assert allowed_tools("logs") == []


# ── 금지 불변 검증 ───────────────────────────────────────────────


def test_no_forbidden_keywords_in_any_mapping() -> None:
    forbidden = re.compile(
        r"\b(" + "|".join(re.escape(kw) for kw in FORBIDDEN_ACTIONS) + r")\b",
        re.IGNORECASE,
    )
    for command in known_commands():
        for tool in allowed_tools(command):
            assert not forbidden.search(tool), (command, tool)


def test_validate_mapping_rejects_forbidden_tool() -> None:
    with pytest.raises(ValueError, match="apply"):
        validate_mapping({"tf-review": ("Bash(terraform apply:*)",)})


def test_validate_mapping_rejects_iam_tool() -> None:
    with pytest.raises(ValueError, match="iam"):
        validate_mapping({"logs": ("Bash(aws iam:*)",)})


def test_validate_mapping_rejects_empty_tool() -> None:
    with pytest.raises(ValueError, match="empty"):
        validate_mapping({"logs": ("  ",)})


def test_validate_mapping_accepts_current_shape() -> None:
    validate_mapping({"logs": ("Bash(aws logs:*)", "Read")})


# ── run_for_command — claude_runner 연결점 ───────────────────────


def test_run_for_command_passes_allowlist_to_runner() -> None:
    runner = RecordingRunner(stdout=_result_json("log analysis"))
    result = run_for_command("logs", "analyze", timeout_s=30, runner=runner)
    assert result.output == "log analysis"
    assert len(runner.calls) == 1
    cmd, timeout_s = runner.calls[0]
    assert timeout_s == 30
    assert cmd == build_command("analyze", [])


def test_run_for_command_threads_mcp_config_to_runner() -> None:
    cfg = '{"mcpServers":{"slackops":{"command":"python","args":["-m","app.mcp_server"]}}}'
    runner = RecordingRunner(stdout=_result_json("ok"))
    run_for_command("logs", "analyze", timeout_s=30, runner=runner, mcp_config=cfg)
    cmd, _ = runner.calls[0]
    assert cmd == build_command("analyze", [], cfg)
    idx = cmd.index("--mcp-config")
    assert cmd[idx + 1] == cfg
    assert "--strict-mcp-config" in cmd


def test_run_for_command_unknown_command_denied_before_runner() -> None:
    runner = RecordingRunner()
    with pytest.raises(PermissionDenied):
        run_for_command("destroy-everything", "p", runner=runner)
    assert runner.calls == []


def test_run_for_command_forbidden_action_denied_before_runner() -> None:
    runner = RecordingRunner()
    with pytest.raises(PermissionDenied):
        run_for_command("apply", "p", runner=runner)
    assert runner.calls == []


def test_run_for_command_ping_has_no_claude_path() -> None:
    """ping 은 권한은 통과하지만 Claude 경로가 없다 — runner 미호출."""
    runner = RecordingRunner()
    with pytest.raises(AllowlistDenied):
        run_for_command("ping", "p", runner=runner)
    assert runner.calls == []


# ── run_for_command — 계측 hook(on_metrics) ──────────────────────


def test_run_for_command_on_metrics_emits_success_metrics() -> None:
    runner = RecordingRunner(stdout=_result_json("ok", cost=0.02))
    captured: list[RunMetrics] = []

    run_for_command("logs", "analyze", runner=runner, on_metrics=captured.append)

    [m] = captured
    assert m.command == "logs"
    assert m.success is True
    assert m.cost_usd == 0.02
    assert m.duration_ms >= 0.0
    assert m.error is None


def test_run_for_command_on_metrics_failure_emits_then_raises() -> None:
    def timeout_runner(cmd: list[str], timeout_s: int) -> tuple[int, str, str]:
        raise subprocess.TimeoutExpired(cmd, timeout_s)

    captured: list[RunMetrics] = []
    with pytest.raises(ClaudeTimeoutError):
        run_for_command(
            "logs", "analyze", runner=timeout_runner, on_metrics=captured.append
        )

    [m] = captured
    assert m.success is False
    assert m.error is not None and "Timeout" in m.error


def test_run_for_command_on_metrics_skipped_when_denied_before_runner() -> None:
    """게이트 거부는 Claude 호출이 아니다 — 계측 emit 없음."""
    captured: list[RunMetrics] = []
    with pytest.raises(PermissionDenied):
        run_for_command(
            "apply", "p", runner=RecordingRunner(), on_metrics=captured.append
        )
    assert captured == []
