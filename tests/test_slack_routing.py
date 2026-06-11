"""SlackHandler 라우팅 테스트 — slack_bolt 미설치 환경에서도 동작(lazy import 설계)."""

from __future__ import annotations

import pytest

from app.slack_handler import USAGE, SlackHandler, build_default_handler


@pytest.fixture
def handler() -> SlackHandler:
    return build_default_handler()


def test_ping_routes_to_handler(handler: SlackHandler) -> None:
    response = handler.route("ping")
    assert "pong" in response
    assert "slackops-devops-agent" in response


def test_empty_text_returns_usage(handler: SlackHandler) -> None:
    assert handler.route("") == USAGE
    assert handler.route("   ") == USAGE


def test_unknown_command_denied(handler: SlackHandler) -> None:
    response = handler.route("rm-rf /")
    assert "허용되지 않은" in response


def test_forbidden_invariant_denied(handler: SlackHandler) -> None:
    """금지 불변(apply/deploy 등)은 라우팅에서 즉시 거부."""
    assert "허용되지 않은" in handler.route("apply now")
    assert "허용되지 않은" in handler.route("deploy prod")


def test_allowed_but_unimplemented_command(handler: SlackHandler) -> None:
    response = handler.route("logs api-service")
    assert "구현되지 않았습니다" in response


def test_subcommand_case_insensitive(handler: SlackHandler) -> None:
    assert "pong" in handler.route("PING")


def test_args_passed_to_handler() -> None:
    captured: list[str] = []
    handler = SlackHandler()
    handler.register("logs", lambda args: captured.append(args) or "ok")
    handler.route("logs  api-service ")
    assert captured == ["api-service"]


def test_register_disallowed_command_rejected() -> None:
    """default deny 우회 방지 — 미정의/금지 명령은 등록 자체가 거부."""
    handler = SlackHandler()
    with pytest.raises(ValueError):
        handler.register("apply", lambda _: "never")
