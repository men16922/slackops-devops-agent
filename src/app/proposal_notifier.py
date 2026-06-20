"""작업 이벤트 알림 — 큐의 생명주기 변화를 Slack 채널로 알린다(팀 인지).

producer/표면 무관: 공유 큐(단일테이블)를 폴링해 **의미 있는 상태 전이**를 한 번씩 게시한다 —
새 작업 적재(누가 web/slack/agent 로 명령했는지), 승인 대기(diff 리뷰 필요), 완료(done) /
실패(failed). 이로써 한 운영자가 웹에서 명령을 돌리거나 작업이 끝나면 **다른 운영자도 채널에서
바로 인지**한다. 에이전트 자율 제안은 그중 한 경우(pending + source=agent)다.

코어(`notify_job_events`)는 **순수 함수** — post_fn 주입으로 테스트 가능, Slack SDK 비의존
(이 모듈은 순수 `app.store.base` 만 import → 미설치 환경 import-safe). main.py(Slack 앱
프로세스)가 Bolt 의 인증된 client 로 이 루프를 데몬 스레드에서 돌린다(별도 프로세스/유닛 불필요).

`seen`(job_id→마지막 알린 status) 으로 중복 게시 방지. run_forever 는 첫 폴링을 **prime**(무게시
기록)으로 처리해 재시작 시 기존 작업 전부를 다시 알리는 스팸을 막는다 — 부팅 이후의 변화만 알린다.
"""

from __future__ import annotations

import os
import time
from typing import TYPE_CHECKING, Any, Callable

from app.store.base import JobSource, JobStatus

if TYPE_CHECKING:
    from app.store.base import Job, JobStore

POLL_INTERVAL_S = 5.0

# 게시 대상 전이 — 새 작업/승인대기/완료/실패. running 등 과도 상태는 제외(노이즈 방지).
NOTIFY_STATUSES: frozenset[str] = frozenset(
    {
        JobStatus.PENDING.value,
        JobStatus.AWAITING_APPROVAL.value,
        JobStatus.DONE.value,
        JobStatus.FAILED.value,
    }
)

# 주입되는 게시 함수 — 테스트는 fake, prod 는 chat_postMessage closure.
PostFn = Callable[[str], None]


def _link(job_id: str) -> str:
    """대시보드 deep-link — DASHBOARD_URL 미설정 시 (job <id>) 폴백."""
    dashboard = os.environ.get("DASHBOARD_URL", "").rstrip("/")
    return f"{dashboard}/jobs/{job_id}" if dashboard else f"(job {job_id})"


def _cost(job: Job) -> str:
    """완료 작업의 비용/토큰 메타(없으면 빈 문자열). Slack 게시는 shortcode 그대로 렌더됨."""
    if job.cost_usd is None and job.tokens is None:
        return ""
    cost = f"${job.cost_usd:.4f}" if job.cost_usd is not None else "—"
    tok = f"{job.tokens} tok" if job.tokens is not None else "—"
    return f" — {cost} · {tok}"


def format_event(job: Job) -> str:
    """작업 1건의 현재 상태를 Slack 메시지 텍스트로 — 상태/소스/근거/비용 + deep-link.

    Slack 으로 게시되므로 이모지는 `:shortcode:`(Slack 이 렌더)를 쓴다.
    """
    link = _link(job.id)
    cmd = f"`{job.command}`" + (f" `{job.args}`" if job.args else "")
    status = job.status.value
    if status == JobStatus.PENDING.value:
        if job.source is JobSource.AGENT:
            why = f"\n> {job.rationale}" if job.rationale else ""
            return f":robot_face: *Agent proposal* — {cmd}{why}\nApprove/reject: {link}"
        actor = job.requested_by or job.source.value
        return f":new: *Queued* {cmd} — by {actor} ({job.source.value})\n{link}"
    if status == JobStatus.AWAITING_APPROVAL.value:
        return f":hourglass: *Awaiting approval* — {cmd}\nReview the diff: {link}"
    if status == JobStatus.DONE.value:
        return f":white_check_mark: *Done* — {cmd}{_cost(job)}\n{link}"
    if status == JobStatus.FAILED.value:
        err = f"\n> {job.error[:200]}" if job.error else ""
        return f":x: *Failed* — {cmd}{err}\n{link}"
    return f"*{status}* — {cmd}\n{link}"


def notify_job_events(
    store: JobStore, post_fn: PostFn, seen: dict[str, str], *, prime: bool = False
) -> list[str]:
    """게시 대상 상태로 **전이한** 작업마다 post_fn 호출 — 새로 알린 job id 목록 반환.

    `seen`(job_id→status)을 in-place 갱신해 같은 상태 재게시를 막는다. prime=True 면 게시 없이
    현재 상태만 기록(부팅 직후 기존 작업 스팸 방지). post 실패 시 seen 을 갱신하지 않아 다음 주기에
    재시도한다. list_recent 는 최신순이라 reversed 로 시간순(오래된 전이 먼저) 게시.
    """
    newly: list[str] = []
    for job in reversed(store.list_recent(50)):
        cur = job.status.value
        worthy = (seen.get(job.id) != cur) and (cur in NOTIFY_STATUSES)
        if prime or not worthy:
            seen[job.id] = cur
            continue
        try:
            post_fn(format_event(job))
        except Exception:  # noqa: BLE001 — 일시 실패(rate limit 등)는 다음 주기 재시도.
            continue
        seen[job.id] = cur
        newly.append(job.id)
    return newly


def run_forever(
    store: JobStore,
    post_fn: PostFn,
    *,
    poll_interval_s: float = POLL_INTERVAL_S,
    max_iterations: int | None = None,
    sleep: Callable[[float], None] | None = None,
    seen: dict[str, str] | None = None,
) -> int:
    """폴링 루프 — 첫 폴링은 prime(무게시 기록), 이후 상태 전이를 게시. worker 패턴 미러.

    Returns 누적 게시 건수. `sleep` 주입으로 테스트에서 실제 대기 없이 max_iterations 만큼 돈다.
    """
    active_sleep = sleep if sleep is not None else time.sleep
    states = seen if seen is not None else {}
    primed = False
    posted = 0
    iterations = 0
    while max_iterations is None or iterations < max_iterations:
        iterations += 1
        posted += len(notify_job_events(store, post_fn, states, prime=not primed))
        primed = True
        active_sleep(poll_interval_s)
    return posted


def make_post_fn(client: Any, channel: str) -> PostFn:
    """Slack WebClient(Bolt `app.client`) + 채널 → post_fn closure(chat_postMessage)."""

    def _post(text: str) -> None:
        client.chat_postMessage(channel=channel, text=text)

    return _post
