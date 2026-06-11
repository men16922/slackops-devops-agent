"""Slack Bolt Socket Mode client + 명령 라우팅.

`/devops <subcommand>` 입력을 파싱해 commands/ 핸들러로 라우팅한다.
**Template Prompt 강제(주입 방어 4계층)** — Slack 입력을 Claude 에 직접 전달하지 않는다.
"""

from __future__ import annotations

from typing import Any, Callable


class SlackHandler:
    """Bolt Socket Mode client 래퍼 + 명령 라우터.

    Attributes:
        app: Slack Bolt App (Socket Mode).
    """

    def __init__(self, app: Any) -> None:
        self.app = app
        self._routes: dict[str, Callable[..., Any]] = {}

    def register(self, subcommand: str, handler: Callable[..., Any]) -> None:
        """`/devops <subcommand>` 핸들러 등록."""
        raise NotImplementedError("Day 1–3: 명령 라우팅 등록 구현 예정")

    def route(self, command_text: str) -> Any:
        """수신한 명령 텍스트를 subcommand 핸들러로 라우팅.

        Args:
            command_text: Slack slash command payload 의 text.
        """
        raise NotImplementedError("Day 1–3: 명령 라우팅 구현 예정")

    def start(self) -> None:
        """Socket Mode 연결 시작(블로킹)."""
        raise NotImplementedError("Day 1–3: Socket Mode 연결 구현 예정")
