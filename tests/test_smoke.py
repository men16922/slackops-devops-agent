"""Import smoke test — stub 모듈이 import 가능한지만 검증.

의존성 미설치 환경에서도 통과하도록, 서드파티(import-time) 의존 없는 stub 만 import 한다.
실 기능 테스트는 Day 계획 진행하며 추가.
"""

from __future__ import annotations

import importlib

import pytest

# import-time 서드파티 의존이 없는 stub 모듈만 (fastapi/slack-bolt/otel 미설치 환경 통과 목적).
STUB_MODULES = [
    "app",
    "app.job_queue",
    "app.permissions",
    "app.sanitizer",
    "app.claude_runner",
    "app.commands",
    "app.commands.ping",
    "app.commands.logs",
    "app.commands.diagnose",
    "app.commands.tf_review",
    "app.commands.pr",
]


@pytest.mark.parametrize("module_name", STUB_MODULES)
def test_module_imports(module_name: str) -> None:
    """각 stub 모듈이 예외 없이 import 된다."""
    assert importlib.import_module(module_name) is not None


def test_permission_levels_mvp() -> None:
    """MVP 활성 레벨은 PREPARE(1) — EXECUTE(2) 비활성 불변 확인."""
    from app.permissions import MAX_ENABLED_LEVEL, PermissionLevel

    assert MAX_ENABLED_LEVEL == PermissionLevel.PREPARE
    assert PermissionLevel.EXECUTE > MAX_ENABLED_LEVEL


def test_sanitizer_tag_constants() -> None:
    """untrusted 격리 태그 상수가 정의되어 있다(주입 방어 1계층)."""
    from app.sanitizer import UNTRUSTED_CLOSE, UNTRUSTED_OPEN

    assert UNTRUSTED_OPEN == "<untrusted_data>"
    assert UNTRUSTED_CLOSE == "</untrusted_data>"
