"""Permission Engine (Level 0/1/2).

명령을 권한 레벨에 매핑하고 허용 여부를 게이트한다.
**MVP 는 Level 0·1 만 활성, Level 2(Execute) 비활성.**
금지 불변: Production 변경, 배포(apply/deploy), IAM 변경, DB 변경.
"""

from __future__ import annotations

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

# subcommand → 요구 권한 레벨. 여기 없는 명령은 전부 거부(default deny).
_COMMAND_LEVELS: dict[str, PermissionLevel] = {
    "ping": PermissionLevel.OBSERVE,
    "logs": PermissionLevel.OBSERVE,
    "diagnose": PermissionLevel.OBSERVE,
    "tf-review": PermissionLevel.PREPARE,
    "pr": PermissionLevel.PREPARE,
}

# 금지 불변 — 레벨과 무관하게 항상 거부되는 행위 키워드(Production/배포/IAM/DB).
FORBIDDEN_ACTIONS: frozenset[str] = frozenset(
    {"apply", "deploy", "rollout", "iam", "db-change", "production"}
)


class PermissionDenied(Exception):
    """권한 게이트 거부."""


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
