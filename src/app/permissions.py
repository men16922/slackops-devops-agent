"""Permission Engine (Level 0/1/2).

명령을 권한 레벨에 매핑하고 허용 여부를 게이트한다.
**MVP 는 Level 0·1 만 활성, Level 2(Execute) 비활성.**
금지 불변: Production 변경, 배포(apply/deploy), IAM 변경, DB 변경.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


class PermissionLevel(IntEnum):
    """권한 레벨.

    OBSERVE(0): logs/describe/get — 읽기 전용.
    PREPARE(1): branch, code modify, unit test, terraform plan, PR 생성.
    EXECUTE(2): apply, rollout restart — **MVP 비활성.**
    """

    OBSERVE = 0
    PREPARE = 1
    EXECUTE = 2


# MVP 에서 활성화된 최대 레벨(EXECUTE 비활성).
MAX_ENABLED_LEVEL: PermissionLevel = PermissionLevel.PREPARE


@dataclass(frozen=True)
class CommandSpec:
    """명령 1개의 권한 사양 — 명령 등록의 단일 진실원(single source of truth).

    Attributes:
        name: subcommand 이름.
        level: 요구 권한 레벨.
        claude_backed: Claude Code Headless 경유 여부. False 면 allowlist 대상 아님
            (예: ping 은 로컬 응답이라 도구 allowlist 가 없다).
    """

    name: str
    level: PermissionLevel
    claude_backed: bool


# 명령 레지스트리(단일 진실원). 레벨/allowlist/핸들러 등록이 모두 이 목록에서 파생된다.
# 새 명령은 여기 한 곳에 추가하고, allowlist._COMMAND_TOOLS 와 slack_handler 등록을 맞춘다 —
# 불일치는 allowlist import 시점에 즉시 에러로 드러난다(allowlist._cross_check_with_permissions).
COMMAND_SPECS: tuple[CommandSpec, ...] = (
    CommandSpec("ping", PermissionLevel.OBSERVE, claude_backed=False),
    CommandSpec("logs", PermissionLevel.OBSERVE, claude_backed=True),
    CommandSpec("diagnose", PermissionLevel.OBSERVE, claude_backed=True),
    CommandSpec("tf-review", PermissionLevel.PREPARE, claude_backed=True),
    CommandSpec("pr", PermissionLevel.PREPARE, claude_backed=True),
    # 거버넌스 탐지 스캔(read-only AWS) — logs/diagnose 와 같은 L0 관찰.
    CommandSpec("detect", PermissionLevel.OBSERVE, claude_backed=True),
)

# subcommand → 요구 권한 레벨(레지스트리에서 파생). 여기 없는 명령은 전부 거부(default deny).
_COMMAND_LEVELS: dict[str, PermissionLevel] = {
    spec.name: spec.level for spec in COMMAND_SPECS
}

# 금지 불변 — 레벨과 무관하게 항상 거부되는 행위 키워드(Production/배포/IAM/DB).
FORBIDDEN_ACTIONS: frozenset[str] = frozenset(
    {"apply", "deploy", "rollout", "iam", "db-change", "production"}
)


class PermissionDenied(Exception):
    """권한 게이트 거부."""


def known_commands() -> frozenset[str]:
    """레지스트리에 정의된 모든 명령 이름(ping 포함)."""
    return frozenset(_COMMAND_LEVELS)


def claude_backed_commands() -> frozenset[str]:
    """Claude Code Headless 를 경유하는 명령(allowlist 대상 — ping 제외)."""
    return frozenset(spec.name for spec in COMMAND_SPECS if spec.claude_backed)


def required_level(command: str) -> PermissionLevel:
    """subcommand 가 요구하는 권한 레벨 반환.

    Args:
        command: subcommand 이름(ping/logs/diagnose/tf-review/pr).

    Raises:
        PermissionDenied: 정의되지 않은 명령(default deny).
    """
    try:
        return _COMMAND_LEVELS[command]
    except KeyError:
        raise PermissionDenied(f"unknown command (default deny): {command!r}") from None


def is_allowed(command: str) -> bool:
    """명령이 현재 활성 레벨(MAX_ENABLED_LEVEL) 내에서 허용되는지.

    EXECUTE(2) 및 금지 불변(Production/배포/IAM/DB)은 항상 거부.
    """
    if command in FORBIDDEN_ACTIONS:
        return False
    try:
        return required_level(command) <= MAX_ENABLED_LEVEL
    except PermissionDenied:
        return False
