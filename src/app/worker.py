"""EC2 Agent Worker — 공유 job queue 폴링 루프 (이중 컨트롤플레인 consumer).

Slack/Web 두 producer 가 넣은 job 을 단일 worker 가 `store.claim()` 으로 원자
소비한다. 실행 결과가 diff(L1 쓰기)면 출력 게이트(주입 방어 3계층)로
AWAITING_APPROVAL 에 멈추고, 아니면 DONE/FAILED 로 종료하며 audit/metric 을
write-back 한다.

모든 외부 의존성은 주입 가능 — store(JobStore/AuditStore/TelemetryStore),
명령 실행기(executors), subprocess 실행기(runner), monotonic/sleep. 단위 테스트는
SqliteJobStore + mock 으로 실 AWS/Claude 호출 없이 e2e 를 검증한다.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable

from app.claude_runner import SubprocessRunner
from app.store import (
    AuditStore,
    Job,
    JobStatus,
    JobStore,
    TelemetryStore,
)
from app.telemetry import RunMetrics, record_run_metrics

# 폴링 간격 기본값(초) — 큐가 비었을 때만 대기한다.
POLL_INTERVAL_S = 2.0

# audit 이벤트의 actor — worker 가 수행한 전이임을 표시.
WORKER_ACTOR = "worker"

# audit action 종류(대시보드/조회가 문자열로 필터하므로 상수로 고정).
AUDIT_CLAIMED = "claimed"
AUDIT_AWAITING_APPROVAL = "awaiting_approval"
AUDIT_DONE = "done"
AUDIT_FAILED = "failed"


@dataclass
class CommandOutcome:
    """명령 실행기 1회 실행의 결과.

    Attributes:
        result: 사용자에게 게시할 결과 텍스트.
        diff: L1 쓰기의 변경 diff. None 이 아니고 job 이 아직 미승인이면
            출력 게이트(AWAITING_APPROVAL)로 분기한다.
        tokens / cost_usd / tool_calls: 계측 메타(없으면 None).
    """

    result: str = ""
    diff: str | None = None
    tokens: int | None = None
    cost_usd: float | None = None
    tool_calls: int | None = None


# 명령 실행기 시그니처: (job) → CommandOutcome. 예외는 worker 가 FAILED 로 기록한다.
CommandExecutor = Callable[[Job], CommandOutcome]


def default_executors(
    runner: SubprocessRunner | None = None,
) -> dict[str, CommandExecutor]:
    """permissions 레지스트리의 MVP 명령에 대한 기본 실행기 매핑 생성.

    핸들러는 호출 시점에 모듈 속성으로 조회한다(slack_handler 와 동일 패턴 —
    테스트에서 monkeypatch 주입 가능). pr 은 PrResult.diff 를 CommandOutcome.diff
    로 연결해 출력 게이트(AWAITING_APPROVAL)로 분기시킨다.

    Args:
        runner: claude-backed 핸들러에 전달할 subprocess 실행기(테스트 주입점).
    """
    from app.commands import diagnose, logs, ping, pr, tf_review

    def _merge_metrics(
        outcome: CommandOutcome, captured: list[RunMetrics]
    ) -> CommandOutcome:
        # run_for_command 가 emit 한 마지막 호출 계측(tokens/cost)을 outcome 에 병합 —
        # 핸들러는 텍스트만 반환하므로 hook 없이는 계측이 유실된다.
        if captured:
            outcome.tokens = captured[-1].tokens
            outcome.cost_usd = captured[-1].cost_usd
        return outcome

    def logs_executor(job: Job) -> CommandOutcome:
        captured: list[RunMetrics] = []
        text = logs.handle_logs(job.args, runner=runner, on_metrics=captured.append)
        return _merge_metrics(CommandOutcome(result=text), captured)

    def diagnose_executor(job: Job) -> CommandOutcome:
        captured: list[RunMetrics] = []
        text = diagnose.handle_diagnose(
            job.args, runner=runner, on_metrics=captured.append
        )
        return _merge_metrics(CommandOutcome(result=text), captured)

    def tf_review_executor(_job: Job) -> CommandOutcome:
        captured: list[RunMetrics] = []
        text = tf_review.handle_tf_review(runner=runner, on_metrics=captured.append)
        return _merge_metrics(CommandOutcome(result=text), captured)

    def pr_executor(job: Job) -> CommandOutcome:
        # 승인된 job(approved_by 기록)만 execute 단계 — job.diff 가 승인된 diff 다.
        approved_diff = job.diff if job.approved_by is not None else None
        captured: list[RunMetrics] = []
        pr_result = pr.handle_pr(
            job.args,
            approved_diff=approved_diff,
            runner=runner,
            on_metrics=captured.append,
        )
        return _merge_metrics(
            CommandOutcome(result=pr_result.summary, diff=pr_result.diff), captured
        )

    return {
        "ping": lambda _job: CommandOutcome(result=ping.handle_ping()),
        "logs": logs_executor,
        "diagnose": diagnose_executor,
        "tf-review": tf_review_executor,
        "pr": pr_executor,
    }


class Worker:
    """공유 job queue 의 단일 consumer.

    process_one() 이 단위 작업(claim→실행→전이+write-back) 1건이고,
    run_forever() 는 그것을 폴링 간격으로 반복한다.
    """

    def __init__(
        self,
        job_store: JobStore,
        audit_store: AuditStore,
        telemetry_store: TelemetryStore,
        *,
        executors: dict[str, CommandExecutor] | None = None,
        runner: SubprocessRunner | None = None,
        monotonic: Callable[[], float] | None = None,
        tracer: Any | None = None,
    ) -> None:
        """worker 구성 — 모든 협력자는 주입 가능.

        Args:
            job_store: 공유 job 큐(claim/await_approval/complete).
            audit_store: 전이마다 감사 이벤트 append.
            telemetry_store: 실행 1건당 metric 기록.
            executors: 명령 → 실행기 매핑. None 이면 default_executors(runner).
                매핑에 없는 명령은 실행 없이 FAILED(default deny).
            runner: 기본 실행기에 전달할 subprocess 실행기(테스트 주입점).
            monotonic: duration_ms 계측용 단조 시계(테스트 주입점).
            tracer: telemetry.setup_telemetry 가 돌려준 OTel tracer. None 이면
                store 기록만 하고 OTel emit 은 생략한다.
        """
        self._jobs = job_store
        self._audit = audit_store
        self._metrics = telemetry_store
        self._executors = (
            executors if executors is not None else default_executors(runner)
        )
        self._monotonic = monotonic if monotonic is not None else time.monotonic
        self._tracer = tracer

    def process_one(self) -> Job | None:
        """claim 가능한 job 1건을 소비 — 실행 → 게이트/종료 전이 + audit/metric.

        실행기 예외는 전파하지 않고 FAILED 로 기록한다(루프 생존).
        store 자체 오류(claim/전이 실패)는 전파한다 — 폴링 재시도가 아니라
        운영자 개입이 필요한 상태다.

        Returns:
            전이가 끝난 최신 Job, 또는 claim 할 job 이 없으면 None.
        """
        job = self._jobs.claim()
        if job is None:
            return None
        self._audit.append(
            job.id, AUDIT_CLAIMED, actor=WORKER_ACTOR, detail=f"command={job.command}"
        )

        started = self._monotonic()
        executor = self._executors.get(job.command)
        try:
            if executor is None:
                raise LookupError(
                    f"no executor for command (default deny): {job.command!r}"
                )
            outcome = executor(job)
        except Exception as exc:  # noqa: BLE001 — 실행 실패를 FAILED 로 기록(루프 생존)
            return self._fail(job, started, exc)

        duration_ms = self._duration_ms(started)
        # 출력 게이트(주입 방어 3계층): diff 가 있는 L1 쓰기는 사람 승인 전에
        # 멈춘다. 이미 승인된 job(approved_by 기록)은 게이트를 재통과하지 않는다.
        # 게이트를 거치는 job(pr)은 prepare/execute 각 1회씩 metric 이 2건 기록된다 —
        # 실행(Claude 호출)이 실제로 2회이므로 의도된 동작(대시보드는 job 단위 집계).
        if outcome.diff is not None and job.approved_by is None:
            updated = self._jobs.await_approval(job.id, outcome.diff)
            self._audit.append(
                job.id,
                AUDIT_AWAITING_APPROVAL,
                actor=WORKER_ACTOR,
                detail=f"diff {len(outcome.diff)} chars",
            )
            self._record(job, duration_ms, outcome, success=True)
            return updated

        updated = self._jobs.complete(
            job.id,
            status=JobStatus.DONE,
            result=outcome.result,
            cost_usd=outcome.cost_usd,
            tokens=outcome.tokens,
        )
        self._audit.append(job.id, AUDIT_DONE, actor=WORKER_ACTOR)
        self._record(job, duration_ms, outcome, success=True)
        return updated

    def run_forever(
        self,
        *,
        poll_interval_s: float = POLL_INTERVAL_S,
        max_iterations: int | None = None,
        sleep: Callable[[float], None] | None = None,
    ) -> int:
        """폴링 루프 — 큐가 비면 sleep, 아니면 즉시 다음 job 을 소비.

        Args:
            poll_interval_s: 큐가 비었을 때 대기 간격(초).
            max_iterations: 폴링 횟수 상한(None 이면 무한 — 운영 모드).
            sleep: 대기 함수(테스트 주입점). None 이면 time.sleep.

        Returns:
            처리(전이 완료)한 job 수.
        """
        active_sleep = sleep if sleep is not None else time.sleep
        processed = 0
        iterations = 0
        while max_iterations is None or iterations < max_iterations:
            iterations += 1
            if self.process_one() is not None:
                processed += 1
            else:
                active_sleep(poll_interval_s)
        return processed

    # ── 내부 ──────────────────────────────────────────────────
    def _duration_ms(self, started: float) -> float:
        return (self._monotonic() - started) * 1000.0

    def _fail(self, job: Job, started: float, exc: Exception) -> Job | None:
        error = f"{type(exc).__name__}: {exc}"
        updated = self._jobs.complete(job.id, status=JobStatus.FAILED, error=error)
        self._audit.append(job.id, AUDIT_FAILED, actor=WORKER_ACTOR, detail=error)
        record_run_metrics(
            self._metrics,
            job.id,
            command=job.command,
            duration_ms=self._duration_ms(started),
            success=False,
            error=error,
            tracer=self._tracer,
        )
        return updated

    def _record(
        self, job: Job, duration_ms: float, outcome: CommandOutcome, *, success: bool
    ) -> None:
        record_run_metrics(
            self._metrics,
            job.id,
            command=job.command,
            duration_ms=duration_ms,
            tokens=outcome.tokens,
            cost_usd=outcome.cost_usd,
            tool_calls=outcome.tool_calls,
            success=success,
            tracer=self._tracer,
        )
