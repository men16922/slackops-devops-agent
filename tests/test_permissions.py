"""Permission Engine 테스트 — 레벨 매핑 / 게이트 / 금지 불변."""

from __future__ import annotations

import pytest

from app.permissions import (
    MAX_ENABLED_LEVEL,
    PermissionDenied,
    PermissionLevel,
    is_allowed,
    required_level,
)


@pytest.mark.parametrize(
    ("command", "level"),
    [
        ("ping", PermissionLevel.OBSERVE),
        ("logs", PermissionLevel.OBSERVE),
        ("diagnose", PermissionLevel.OBSERVE),
        ("tf-review", PermissionLevel.PREPARE),
        ("pr", PermissionLevel.PREPARE),
    ],
)
def test_required_level(command: str, level: PermissionLevel) -> None:
    assert required_level(command) == level


def test_unknown_command_default_deny() -> None:
    with pytest.raises(PermissionDenied):
        required_level("rm-rf")
    assert not is_allowed("rm-rf")


@pytest.mark.parametrize("command", ["ping", "logs", "diagnose", "tf-review", "pr"])
def test_mvp_commands_allowed(command: str) -> None:
    assert is_allowed(command)


@pytest.mark.parametrize(
    "forbidden", ["apply", "deploy", "rollout", "iam", "db-change", "production"]
)
def test_forbidden_invariants_always_denied(forbidden: str) -> None:
    """금지 불변(Production/배포/IAM/DB)은 레벨과 무관하게 거부."""
    assert not is_allowed(forbidden)


def test_execute_level_disabled_in_mvp() -> None:
    assert MAX_ENABLED_LEVEL < PermissionLevel.EXECUTE
