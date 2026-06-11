"""테스트 공용 헬퍼 — 주입용 mock 실행기/fetcher 와 result JSON 빌더.

claude_runner/allowlist/logs/diagnose 테스트가 동일한 mock 을 복붙하지 않도록 한 곳에 둔다.
(test_ prefix 가 없어 pytest 가 테스트로 수집하지 않는다.)
"""

from __future__ import annotations

import json


class RecordingRunner:
    """주입용 mock subprocess 실행기 — 호출 (cmd, timeout_s) 를 기록하고 고정 응답 반환.

    SubprocessRunner 규약과 동일하게 (exit_code, stdout, stderr) 를 돌려준다.
    """

    def __init__(self, stdout: str = "", exit_code: int = 0, stderr: str = "") -> None:
        self.stdout = stdout
        self.exit_code = exit_code
        self.stderr = stderr
        self.calls: list[tuple[list[str], int]] = []

    def __call__(self, cmd: list[str], timeout_s: int) -> tuple[int, str, str]:
        self.calls.append((cmd, timeout_s))
        return self.exit_code, self.stdout, self.stderr


class RecordingFetcher:
    """주입용 mock 소스 fetcher — 호출 service 를 기록하고 고정 내용 반환."""

    def __init__(self, content: str = "INFO ok") -> None:
        self.content = content
        self.calls: list[str] = []

    def __call__(self, service: str) -> str:
        self.calls.append(service)
        return self.content


def result_json(result: str = "ok", cost: float = 0.01) -> str:
    """claude `--output-format json` 성공 출력의 최소 형태(result + 비용)."""
    return json.dumps({"result": result, "total_cost_usd": cost})
