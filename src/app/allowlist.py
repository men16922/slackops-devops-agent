"""Tool Allowlist (주입 방어 2계층) — 명령별 허용 도구 사전 정의.

각 Slack 명령이 Claude Code Headless 에서 사용할 수 있는 도구를 사전에 고정한다.
여기 정의되지 않은 명령은 전부 거부(default deny). `ping` 은 Claude 를 경유하지
않으므로 의도적으로 매핑에 없다.

도구 문자열은 Claude Code `--allowedTools` 패턴 문법(`Bash(aws logs:*)`, `Read` 등).
`run_for_command` 가 permissions 게이트 → allowlist 조회 → claude_runner 위임의
단일 진입점이다 — commands/*.py 는 run_headless 를 직접 호출하지 않는다.
"""

from __future__ import annotations

import re
from collections.abc import Mapping

from app import permissions
from app.claude_runner import (
    DEFAULT_TIMEOUT_S,
    RunResult,
    SubprocessRunner,
    run_headless,
)


class AllowlistDenied(Exception):
    """allowlist 에 정의되지 않은 명령(default deny)."""


# 명령 → 허용 도구. 읽기 전용(L0)은 조회 명령만, L1(pr)은 branch→수정→test→PR 경로만.
# 금지 불변(apply/deploy/rollout/iam/db/production)에 해당하는 도구는 어떤 명령에도 없다 —
# 모듈 로드 시 validate_mapping 으로 강제한다.
_COMMAND_TOOLS: dict[str, tuple[str, ...]] = {
    "logs": ("Bash(aws logs:*)",),
    "diagnose": (
        "Bash(aws logs:*)",
        "Bash(kubectl get:*)",
        "Bash(kubectl describe:*)",
        "Bash(git diff:*)",
        "Bash(git log:*)",
        "Read",
    ),
    "tf-review": (
        "Bash(terraform plan:*)",
        "Bash(terraform show:*)",
        "Read",
    ),
    "pr": (
        "Read",
        "Edit",
        "Write",
        "Bash(git status:*)",
        "Bash(git diff:*)",
        "Bash(git checkout:*)",
        "Bash(git add:*)",
        "Bash(git commit:*)",
        "Bash(git push:*)",
        "Bash(gh pr create:*)",
        "Bash(python -m pytest:*)",
    ),
}

# 금지 불변 키워드가 도구 문자열에 단어 단위로 등장하면 매핑 자체를 거부한다.
_FORBIDDEN_TOOL_RE = re.compile(
    r"\b(" + "|".join(re.escape(kw) for kw in sorted(permissions.FORBIDDEN_ACTIONS)) + r")\b",
    re.IGNORECASE,
)


def validate_mapping(mapping: Mapping[str, tuple[str, ...]]) -> None:
    """allowlist 매핑이 금지 불변을 위반하지 않는지 검증.

    Raises:
        ValueError: 빈 도구 문자열이 있거나, 금지 키워드(apply/deploy/rollout/iam/
            db-change/production)가 도구 패턴에 포함된 경우.
    """
    for command, tools in mapping.items():
        for tool in tools:
            if not tool.strip():
                raise ValueError(f"empty tool pattern in allowlist for {command!r}")
            match = _FORBIDDEN_TOOL_RE.search(tool)
            if match:
                raise ValueError(
                    f"forbidden keyword {match.group(0)!r} in allowlist "
                    f"for {command!r}: {tool!r}"
                )


validate_mapping(_COMMAND_TOOLS)


def known_commands() -> frozenset[str]:
    """allowlist 에 정의된 명령 집합(Claude 경유 명령만 — ping 제외)."""
    return frozenset(_COMMAND_TOOLS)


def allowed_tools(command: str) -> list[str]:
    """명령에 허용된 도구 목록 반환(호출자가 변형해도 원본 불변).

    Args:
        command: subcommand 이름(logs/diagnose/tf-review/pr).

    Raises:
        AllowlistDenied: allowlist 에 정의되지 않은 명령(default deny).
    """
    try:
        return list(_COMMAND_TOOLS[command])
    except KeyError:
        raise AllowlistDenied(
            f"no tool allowlist for command (default deny): {command!r}"
        ) from None


def run_for_command(
    command: str,
    prompt: str,
    timeout_s: int = DEFAULT_TIMEOUT_S,
    runner: SubprocessRunner | None = None,
) -> RunResult:
    """명령의 allowlist 를 강제해 Claude Code Headless 를 실행하는 단일 진입점.

    permissions 게이트(레벨 + 금지 불변) → allowlist 조회 → run_headless 순서로,
    어느 단계든 거부되면 subprocess 는 실행되지 않는다.

    Args:
        command: subcommand 이름(logs/diagnose/tf-review/pr).
        prompt: sanitizer.build_prompt 로 생성된 검증된 프롬프트.
        timeout_s: 실행 타임아웃(초).
        runner: subprocess 실행기(테스트 주입점). None 이면 실 subprocess.

    Raises:
        permissions.PermissionDenied: 권한 레벨 초과/미정의/금지 불변.
        AllowlistDenied: 권한은 통과했지만 allowlist 에 없는 명령(예: ping).
    """
    if not permissions.is_allowed(command):
        raise permissions.PermissionDenied(
            f"command not allowed by permission engine: {command!r}"
        )
    return run_headless(
        prompt, allowed_tools(command), timeout_s=timeout_s, runner=runner
    )
