"""제안 알림 — 새 AGENT 제안이 큐에 들어오면 Slack 채널로 알린다.

producer 무관: 공유 큐(단일테이블)를 폴링해 새 PENDING/AWAITING_APPROVAL + source=AGENT
작업을 한 번씩 Slack 에 게시한다 — agent_monitor·chat_agent 제안 모두 캐치한다. 코어
(`notify_new_proposals`)는 **순수 함수** — post_fn 주입으로 테스트 가능하고 Slack SDK 비의존
(이 모듈은 순수 `app.store.base` 만 import → 미설치 환경 import-safe).

main.py(Slack 앱 프로세스)가 Bolt 의 인증된 client 로 이 루프를 데몬 스레드에서 돌린다
(별도 프로세스/유닛 불필요). 인메모리 `seen` 셋으로 중복 게시 방지 — 재시작 시 아직 열린
제안을 1회 재게시(허용 범위; 영속 플래그는 production 업그레이드).
"""

from __future__ import annotations

import os
import time
from typing import TYPE_CHECKING, Any, Callable

from app.store.base import JobSource, JobStatus

if TYPE_CHECKING:
    from app.store.base import Job, JobStore

POLL_INTERVAL_S = 5.0

# 알림 대상 = 아직 사람 조치 전(열린) 제안.
_OPEN_STATUSES: frozenset[str] = frozenset(
    {JobStatus.PENDING.value, JobStatus.AWAITING_APPROVAL.value}
)

# 주입되는 게시 함수 — 테스트는 fake, prod 는 chat_postMessage closure.
PostFn = Callable[[str], None]


def format_proposal(job: Job) -> str:
    """제안 1건을 Slack 메시지 텍스트로 — command/args/rationale + 대시보드 deep-link.

    DASHBOARD_URL 미설정 시 깨진 링크 대신 `(job <id>)` 텍스트로 폴백.
    """
    dashboard = os.environ.get("DASHBOARD_URL", "").rstrip("/")
    link = f"{dashboard}/jobs/{job.id}" if dashboard else f"(job {job.id})"
    args = f" `{job.args}`" if job.args else ""
    why = f"\n> {job.rationale}" if job.rationale else ""
    return (
        f":robot_face: *New agent proposal* — `{job.command}`{args}{why}\n"
        f"Approve/reject: {link}"
    )


def notify_new_proposals(store: JobStore, post_fn: PostFn, seen: set[str]) -> list[str]:
    """아직 알리지 않은 열린 AGENT 제안마다 post_fn 호출 — 새로 알린 job id 목록 반환.

    `seen` 을 in-place 갱신(중복 게시 방지). post_fn 성공 후에만 seen 에 추가 — 실패 시
    다음 주기 재시도. 작업별 try/except 로 한 건 실패가 뒤 건을 막지 않는다. list_recent 는
    최신순이라 reversed 로 시간순(오래된 제안 먼저) 게시.
    """
    newly: list[str] = []
    for job in reversed(store.list_recent(50)):
        if (
            job.source is JobSource.AGENT
            and job.status.value in _OPEN_STATUSES
            and job.id not in seen
        ):
            try:
                post_fn(format_proposal(job))
            except Exception:  # noqa: BLE001 — 일시 실패(rate limit 등)는 다음 주기 재시도.
                continue
            seen.add(job.id)
            newly.append(job.id)
    return newly


def run_forever(
    store: JobStore,
    post_fn: PostFn,
    *,
    poll_interval_s: float = POLL_INTERVAL_S,
    max_iterations: int | None = None,
    sleep: Callable[[float], None] | None = None,
    seen: set[str] | None = None,
) -> int:
    """폴링 루프 — 새 제안을 알리고 sleep. worker/chat_agent run_forever 패턴 미러.

    Returns 누적 게시 건수. `seen` 은 주입 가능(테스트), 기본 새 셋. `sleep` 주입으로
    테스트에서 실제 대기 없이 max_iterations 만큼 돌린다.
    """
    active_sleep = sleep if sleep is not None else time.sleep
    seen_ids = seen if seen is not None else set()
    posted = 0
    iterations = 0
    while max_iterations is None or iterations < max_iterations:
        iterations += 1
        posted += len(notify_new_proposals(store, post_fn, seen_ids))
        active_sleep(poll_interval_s)
    return posted


def make_post_fn(client: Any, channel: str) -> PostFn:
    """Slack WebClient(Bolt `app.client`) + 채널 → post_fn closure(chat_postMessage)."""

    def _post(text: str) -> None:
        client.chat_postMessage(channel=channel, text=text)

    return _post
