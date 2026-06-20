"""SlackHandler 라우팅 테스트 — slack_bolt 미설치 환경에서도 동작(lazy import 설계)."""

from __future__ import annotations

import pytest

from app.allowlist import AllowlistDenied
from app.claude_runner import ClaudeTimeoutError
from app.permissions import PermissionDenied
from app.slack_handler import USAGE, SlackHandler, build_default_handler


def _handler_raising(exc: Exception) -> SlackHandler:
    """logs 핸들러가 주어진 예외를 던지도록 등록한 SlackHandler."""

    def _boom(_args: str) -> str:
        raise exc

    handler = SlackHandler()
    handler.register("logs", _boom)
    return handler


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
    assert "not an allowed command" in response


def test_forbidden_invariant_denied(handler: SlackHandler) -> None:
    """금지 불변(apply/deploy 등)은 라우팅에서 즉시 거부."""
    assert "not an allowed command" in handler.route("apply now")
    assert "not an allowed command" in handler.route("deploy prod")


def test_allowed_but_unregistered_command(handler: SlackHandler) -> None:
    """pr 은 동기 경로 미등록(출력 게이트는 job queue 경유) — '구현 예정' 응답."""
    response = handler.route("pr fix typo")
    assert "not implemented" in response


def test_tf_review_routes_to_handler(
    handler: SlackHandler, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "app.commands.tf_review.handle_tf_review", lambda: "tf-ok"
    )
    assert handler.route("tf-review") == "tf-ok"


def test_detect_routes_to_handler(
    handler: SlackHandler, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`/devops detect <category>` 동기 경로 등록 — 핸들러에 카테고리 인자 전달."""
    monkeypatch.setattr(
        "app.commands.detect.handle_detect", lambda args: f"scan {args}"
    )
    assert handler.route("detect iam") == "scan iam"


def test_logs_routes_to_logs_handler(
    handler: SlackHandler, monkeypatch: pytest.MonkeyPatch
) -> None:
    """logs 라우팅 — 핸들러는 호출 시점 모듈 속성 조회라 monkeypatch 주입이 통한다."""
    captured: list[str] = []
    monkeypatch.setattr(
        "app.commands.logs.handle_logs",
        lambda args: captured.append(args) or "logs-ok",
    )
    assert handler.route("logs  api-service ") == "logs-ok"
    assert captured == ["api-service"]


def test_diagnose_routes_to_diagnose_handler(
    handler: SlackHandler, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: list[str] = []
    monkeypatch.setattr(
        "app.commands.diagnose.handle_diagnose",
        lambda args: captured.append(args) or "diagnose-ok",
    )
    assert handler.route("diagnose api-service") == "diagnose-ok"
    assert captured == ["api-service"]


def test_logs_empty_args_rejected_before_execution(handler: SlackHandler) -> None:
    """인자 없는 logs 는 service 검증에서 거부 — fetcher/Claude 호출 전에 끝난다."""
    assert "service name" in handler.route("logs")


def test_diagnose_empty_args_rejected_before_execution(handler: SlackHandler) -> None:
    assert "service name" in handler.route("diagnose")


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


# ── route 예외 매핑 (finding #1: 핸들러 예외가 Slack 무응답으로 새지 않게) ──


def test_route_maps_timeout_to_slack_message() -> None:
    reply = _handler_raising(ClaudeTimeoutError("timed out")).route("logs svc")
    assert "timed out" in reply


def test_route_maps_permission_denied_to_slack_message() -> None:
    reply = _handler_raising(PermissionDenied("nope")).route("logs svc")
    assert "permission" in reply


def test_route_maps_allowlist_denied_to_slack_message() -> None:
    reply = _handler_raising(AllowlistDenied("no tools")).route("logs svc")
    assert "denied" in reply


def test_route_never_raises_on_unexpected_handler_error() -> None:
    """boto3 등 예상 못한 예외도 메시지로 변환 — ack 후 respond 가 반드시 불린다."""
    reply = _handler_raising(RuntimeError("boto3 ResourceNotFound")).route("logs svc")
    assert "unexpected error" in reply
    assert "RuntimeError" in reply
