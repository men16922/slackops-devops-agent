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

# subcommand 핸들러 시그니처: (args_text) -> Slack 게시용 응답 텍스트.
CommandHandler = Callable[[str], str]

USAGE = (
    "사용법: `/devops <command> [args]`\n"
    "commands: `ping` · `logs <service>` · `diagnose <service>` · `tf-review` · `pr <설명>`"
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
            return f":no_entry: `{subcommand}` 는 허용되지 않은 명령입니다.\n{USAGE}"
        handler = self._routes.get(subcommand)
        if handler is None:
            return f":construction: `{subcommand}` 는 아직 구현되지 않았습니다."
        return handler(rest.strip())

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
    """
    from app.commands.ping import handle_ping

    handler.register("ping", lambda _args: handle_ping())
    return handler


def build_default_handler(app: Any = None) -> SlackHandler:
    """MVP 기본 명령이 등록된 새 SlackHandler 구성(라우팅 테스트용)."""
    return register_default_commands(SlackHandler(app))
