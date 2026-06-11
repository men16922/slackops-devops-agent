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


def required_level(command: str) -> PermissionLevel:
    """subcommand 가 요구하는 권한 레벨 반환.

    Args:
        command: subcommand 이름(ping/logs/diagnose/tf_review/pr).
    """
    raise NotImplementedError("Day 4–5: 명령→레벨 매핑 구현 예정")


def is_allowed(command: str) -> bool:
    """명령이 현재 활성 레벨(MAX_ENABLED_LEVEL) 내에서 허용되는지.

    EXECUTE(2) 및 금지 불변(Production/배포/IAM/DB)은 항상 거부.
    """
    raise NotImplementedError("Day 4–5: 권한 게이트 구현 예정")
