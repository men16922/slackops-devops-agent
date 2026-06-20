"""Slack Bolt Socket Mode client + 명령 라우팅.

`/devops <subcommand> [args]` 입력을 파싱해 commands/ 핸들러로 라우팅한다.
**Template Prompt 강제(주입 방어 4계층)** — Slack 원문은 라우팅 파싱에만 쓰이고,
핸들러에는 분리된 인자 문자열만 전달된다. Claude 프롬프트는 핸들러 내부에서
sanitizer.build_prompt(template 경유)로만 생성한다.

slack_bolt 는 lazy import — 미설치 환경에서도 모듈 import 와 라우팅 로직 테스트가 가능.
"""

from __future__ import annotations

import os
from typing import Any, Callable

from app import permissions
from app.allowlist import AllowlistDenied
from app.claude_runner import ClaudeRunnerError, ClaudeTimeoutError

# subcommand 핸들러 시그니처: (args_text) -> Slack 게시용 응답 텍스트.
CommandHandler = Callable[[str], str]

USAGE = (
    "Usage: `/devops <command> [args]`\n"
    "commands: `ping` · `logs <service>` · `diagnose <service>` · `tf-review` · `pr <description>`"
)


class SlackHandler:
    """Bolt Socket Mode client 래퍼 + 명령 라우터.

    Attributes:
        app: Slack Bolt App (Socket Mode). 라우팅 단위 테스트에서는 None 허용.
    """

    def __init__(self, app: Any = None) -> None:
        self.app = app
        self._routes: dict[str, CommandHandler] = {}

    @classmethod
    def from_env(cls) -> SlackHandler:
        """환경 변수(SLACK_BOT_TOKEN 등)로 Bolt App 을 만들어 핸들러 구성."""
        from slack_bolt import App  # lazy: 미설치 환경 import-safe

        app = App(
            token=os.environ["SLACK_BOT_TOKEN"],
            signing_secret=os.environ.get("SLACK_SIGNING_SECRET", ""),
        )
        handler = cls(app)
        handler._bind_slash_command()
        return handler

    def register(self, subcommand: str, handler: CommandHandler) -> None:
        """`/devops <subcommand>` 핸들러 등록.

        Raises:
            ValueError: permission engine 에 정의되지 않은 명령(default deny 우회 방지).
        """
        if not permissions.is_allowed(subcommand):
            raise ValueError(f"cannot register disallowed command: {subcommand!r}")
        self._routes[subcommand] = handler

    def route(self, command_text: str) -> str:
        """수신한 명령 텍스트를 subcommand 핸들러로 라우팅.

        파싱 → permission 게이트 → 핸들러 호출. 거부/미구현은 사용자 메시지로 응답.

        Args:
            command_text: Slack slash command payload 의 text.

        Returns:
            Slack 에 게시할 응답 텍스트.
        """
        text = command_text.strip()
        if not text:
            return USAGE
        subcommand, _, rest = text.partition(" ")
        subcommand = subcommand.lower()
        if not permissions.is_allowed(subcommand):
            return f":no_entry: `{subcommand}` is not an allowed command.\n{USAGE}"
        handler = self._routes.get(subcommand)
        if handler is None:
            return f":construction: `{subcommand}` is not implemented yet."
        # 핸들러 예외를 Slack 메시지로 매핑하는 최종 안전망 — ack() 후 respond() 가
        # 반드시 불리도록, 어떤 예외도 무응답(silent crash)으로 새지 않게 한다.
        try:
            return handler(rest.strip())
        except permissions.PermissionDenied:
            return f":no_entry: `{subcommand}` was denied by the permission policy."
        except AllowlistDenied:
            return f":no_entry: `{subcommand}` has no allowed tools, so execution was denied."
        except ClaudeTimeoutError:
            return (
                f":hourglass: `{subcommand}` timed out. "
                "Please try again shortly."
            )
        except ClaudeRunnerError:
            return f":warning: An error occurred while running `{subcommand}`."
        except Exception as exc:  # noqa: BLE001 — 최종 안전망: 무응답 방지가 목적
            return (
                f":warning: An unexpected error occurred while handling `{subcommand}` "
                f"({type(exc).__name__}). Check the server logs."
            )

    def _bind_slash_command(self) -> None:
        """Bolt App 에 `/devops` slash command 핸들러 바인딩."""

        def _on_devops(ack: Callable[[], None], respond: Callable[..., None], command: dict[str, Any]) -> None:
            ack()
            respond(self.route(command.get("text", "")))

        self.app.command("/devops")(_on_devops)

    def start(self) -> None:
        """Socket Mode 연결 시작(블로킹). SLACK_APP_TOKEN 필요."""
        from slack_bolt.adapter.socket_mode import SocketModeHandler  # lazy

        SocketModeHandler(self.app, os.environ["SLACK_APP_TOKEN"]).start()


def register_default_commands(handler: SlackHandler) -> SlackHandler:
    """MVP 기본 명령을 기존 SlackHandler 에 등록.

    구현된 명령만 등록 — 미등록 명령은 route 에서 "구현 예정" 응답.
    핸들러는 호출 시점에 모듈 속성으로 조회한다(테스트에서 monkeypatch 주입 가능).
    pr 은 의도적으로 동기 경로에 등록하지 않는다 — 출력 게이트(AWAITING_APPROVAL)가
    store 상태를 요구하므로 job queue(worker) 경유로만 실행한다.
    """
    from app.commands import diagnose, logs, ping, tf_review

    handler.register("ping", lambda _args: ping.handle_ping())
    handler.register("logs", lambda args: logs.handle_logs(args))
    handler.register("diagnose", lambda args: diagnose.handle_diagnose(args))
    handler.register("tf-review", lambda _args: tf_review.handle_tf_review())
    return handler


def build_default_handler(app: Any = None) -> SlackHandler:
    """MVP 기본 명령이 등록된 새 SlackHandler 구성(라우팅 테스트용)."""
    return register_default_commands(SlackHandler(app))
