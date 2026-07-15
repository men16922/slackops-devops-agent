"""command_guard — argv 정규화 + 인자 스키마가 실제 실행 경계인지 검증.

`--allowedTools` 는 명령줄 앞부분만 검사한다(Claude Code 2.1.210 실측: `Bash(echo:*)`
로 제한해도 `echo hi; whoami` 가 실행됨). 여기서 잠그는 것은 그 뒤에 붙는 모든 것이다.
"""

from __future__ import annotations

import json

import pytest

from app import allowlist
from app.claude_runner import build_command, guard_hook_argv
from app.command_guard import (
    GUARD_COMMAND_ENV,
    CommandGuardError,
    hook_decision,
    hook_settings_json,
    known_commands,
    normalize,
    validate,
)


class TestNormalize:
    def test_plain_command_splits_to_argv(self) -> None:
        assert normalize("git status --porcelain") == ("git", "status", "--porcelain")

    def test_quoted_value_survives(self) -> None:
        assert normalize('git commit -m "fix the thing"') == (
            "git",
            "commit",
            "-m",
            "fix the thing",
        )

    @pytest.mark.parametrize(
        "command_line",
        [
            "git diff; whoami",
            "git diff && curl http://evil",
            "git diff | tee /tmp/x",
            "git diff `whoami`",
            "git diff $(whoami)",
            "git diff ${HOME}",
            "git diff > /tmp/out",
            "git diff < /etc/passwd",
            "git status &",
            "git add *",
            "git diff ~/secrets",
            "git diff\nwhoami",
            "git diff \\\n whoami",
        ],
    )
    def test_shell_constructs_are_rejected(self, command_line: str) -> None:
        with pytest.raises(CommandGuardError, match="forbidden shell construct"):
            normalize(command_line)

    def test_parent_traversal_is_rejected(self) -> None:
        with pytest.raises(CommandGuardError, match="traversal"):
            normalize("git add ../../etc/passwd")

    def test_absolute_path_is_rejected(self) -> None:
        with pytest.raises(CommandGuardError, match="absolute path"):
            normalize("git add /etc/passwd")

    def test_empty_is_rejected(self) -> None:
        with pytest.raises(CommandGuardError, match="empty command"):
            normalize("   ")


class TestValidate:
    @pytest.mark.parametrize(
        "command_line",
        [
            "git status --porcelain",
            "git diff HEAD --no-ext-diff --binary",
            "git checkout -b feature/fix-checkout",
            "git add src/app/worker.py",
            'git commit -m "fix: handle empty diff"',
            "git push -u origin feature/fix-checkout",
            'gh pr create --title "fix" --body "detail" --base main',
            "python -m pytest tests/ -q",
        ],
    )
    def test_pr_schema_allows_the_prepared_workflow(self, command_line: str) -> None:
        assert validate("pr", command_line)

    @pytest.mark.parametrize(
        "command_line",
        [
            "whoami",
            "curl http://169.254.169.254/latest/meta-data/",
            "cat /etc/slackops-devops-agent.runtime.env",
            "git config --global user.email attacker@evil.test",
            "git push --force origin main",
            "gh pr merge 42",
            "gh api /user",
            "env",
            "python -c import os",
            "terraform apply",
        ],
    )
    def test_pr_schema_denies_everything_else(self, command_line: str) -> None:
        with pytest.raises(CommandGuardError):
            validate("pr", command_line)

    def test_tf_review_cannot_reach_apply(self) -> None:
        assert validate("tf-review", "terraform plan -no-color")
        with pytest.raises(CommandGuardError):
            validate("tf-review", "terraform apply")

    @pytest.mark.parametrize("command", ["logs", "diagnose", "detect"])
    def test_read_commands_have_no_shell_surface(self, command: str) -> None:
        # 이 명령들의 AWS 데이터는 앱 측 고정 read adapter 가 수집한다 — 모델에 shell 없음.
        with pytest.raises(CommandGuardError, match="may not run shell commands"):
            validate(command, "aws logs describe-log-groups")

    def test_unknown_command_is_default_deny(self) -> None:
        with pytest.raises(CommandGuardError, match="default deny"):
            validate("rm-rf", "git status")

    def test_flag_value_is_bounded(self) -> None:
        with pytest.raises(CommandGuardError):
            validate("pr", "git commit -m " + '"' + "x" * 2500 + '"')


class TestHookDecision:
    def _payload(self, command_line: str) -> dict[str, object]:
        return {
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": command_line, "description": "d"},
        }

    def _decision(self, raw: str) -> dict[str, str]:
        parsed = json.loads(raw)["hookSpecificOutput"]
        assert parsed["hookEventName"] == "PreToolUse"
        return dict(parsed)

    def test_allows_schema_match(self) -> None:
        out = self._decision(hook_decision(self._payload("git status"), "pr"))
        assert out["permissionDecision"] == "allow"

    def test_denies_chained_command(self) -> None:
        out = self._decision(hook_decision(self._payload("git diff; whoami"), "pr"))
        assert out["permissionDecision"] == "deny"
        assert "forbidden shell construct" in out["permissionDecisionReason"]

    def test_denies_when_guard_command_missing(self) -> None:
        # 런타임이 guard 를 구성하지 않았으면 shell 을 열어주지 않는다(fail closed).
        out = self._decision(hook_decision(self._payload("git status"), None))
        assert out["permissionDecision"] == "deny"

    def test_denies_malformed_tool_input(self) -> None:
        payload: dict[str, object] = {"tool_name": "Bash", "tool_input": "not-a-dict"}
        out = self._decision(hook_decision(payload, "pr"))
        assert out["permissionDecision"] == "deny"

    def test_non_bash_tool_is_untouched(self) -> None:
        payload: dict[str, object] = {"tool_name": "Read", "tool_input": {"file": "x"}}
        out = self._decision(hook_decision(payload, "pr"))
        assert out["permissionDecision"] == "allow"


class TestRunnerWiring:
    def test_build_command_installs_the_hook(self) -> None:
        cmd = build_command("prompt", ["Read"], None, "pr")
        assert "--settings" in cmd
        settings = json.loads(cmd[cmd.index("--settings") + 1])
        hook = settings["hooks"]["PreToolUse"][0]
        assert hook["matcher"] == "Bash"
        assert "app.command_guard" in hook["hooks"][0]["command"]

    def test_build_command_without_guard_has_no_settings(self) -> None:
        assert "--settings" not in build_command("prompt", ["Read"])

    def test_hook_settings_json_is_valid_and_quoted(self) -> None:
        settings = json.loads(hook_settings_json(guard_hook_argv()))
        assert settings["hooks"]["PreToolUse"][0]["hooks"][0]["type"] == "command"

    def test_guard_env_carries_the_trusted_command_name(self) -> None:
        from app.claude_runner import _guard_env

        env = _guard_env("pr")
        assert env[GUARD_COMMAND_ENV] == "pr"
        # hook 은 claude 의 자식이므로 app 패키지를 import 할 수 있어야 한다.
        assert env["PYTHONPATH"].endswith("src")

    def test_allowlist_and_guard_cover_the_same_commands(self) -> None:
        # import 시점 cross-check 와 같은 불변 — 한쪽에만 명령이 추가되면 경계가 어긋난다.
        assert allowlist.known_commands() == known_commands()
