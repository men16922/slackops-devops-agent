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

import argparse
import os
import time
from dataclasses import dataclass
from typing import Any, Callable

from app.claude_runner import SubprocessRunner
from app.execution_plan import (
    ExecutionPlan,
    ExecutionPlanError,
    build_pr_plan,
    verify_pr_workspace,
    verify_remote_pr_diff,
)
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
AUDIT_POSTCONDITION_VERIFIED = "postcondition_verified"


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
PlanBuilder = Callable[[Job, str], ExecutionPlan]
ExecutionVerifier = Callable[[Job], ExecutionPlan]
PostconditionVerifier = Callable[[Job, CommandOutcome, ExecutionPlan], None]


def _build_pr_plan(job: Job, diff: str) -> ExecutionPlan:
    return build_pr_plan(job.args, diff, execution_tools=_pr_execution_tools())


def _pr_execution_tools() -> tuple[str, ...]:
    from app.allowlist import allowed_tools
    from app.commands.pr import PR_EXECUTE_EXCLUDED_TOOLS

    return tuple(tool for tool in allowed_tools("pr") if tool not in PR_EXECUTE_EXCLUDED_TOOLS)


def _verify_approved_pr(job: Job) -> ExecutionPlan:
    if (
        job.diff is None
        or job.execution_plan is None
        or job.execution_plan_hash is None
        or job.approval_hash != job.execution_plan_hash
    ):
        raise ExecutionPlanError("approved PR has no matching execution-plan hash")
    return verify_pr_workspace(
        job.args,
        job.diff,
        job.execution_plan,
        job.execution_plan_hash,
        expected_execution_tools=_pr_execution_tools(),
    )


def _verify_pr_postcondition(
    _job: Job, outcome: CommandOutcome, plan: ExecutionPlan
) -> None:
    verify_remote_pr_diff(outcome.result, plan)


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
    from app.commands import detect, diagnose, logs, ping, pr, tf_review

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

    def detect_executor(job: Job) -> CommandOutcome:
        # job.args = 탐지 카테고리(iam/config/ssm/incident). scan-as-job — findings = 결과.
        captured: list[RunMetrics] = []
        text = detect.handle_detect(job.args, runner=runner, on_metrics=captured.append)
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
        "detect": detect_executor,
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
        plan_builder: PlanBuilder | None = None,
        execution_verifier: ExecutionVerifier | None = None,
        postcondition_verifier: PostconditionVerifier | None = None,
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
            plan_builder: PR prepare diff 를 immutable execution plan 으로 만드는 함수.
            execution_verifier: 승인 후 실제 workspace/diff 를 재검증하는 함수.
            postcondition_verifier: 원격 PR 결과가 승인 plan 과 같은지 검증하는 함수.
        """
        self._jobs = job_store
        self._audit = audit_store
        self._metrics = telemetry_store
        self._executors = (
            executors if executors is not None else default_executors(runner)
        )
        self._monotonic = monotonic if monotonic is not None else time.monotonic
        self._tracer = tracer
        self._plan_builder = plan_builder if plan_builder is not None else _build_pr_plan
        self._execution_verifier = (
            execution_verifier if execution_verifier is not None else _verify_approved_pr
        )
        self._postcondition_verifier = (
            postcondition_verifier
            if postcondition_verifier is not None
            else _verify_pr_postcondition
        )

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
            job.id,
            AUDIT_CLAIMED,
            actor=WORKER_ACTOR,
            detail=f"command={job.command}",
            context={"command": job.command},
        )

        started = self._monotonic()
        executor = self._executors.get(job.command)
        try:
            if executor is None:
                raise LookupError(
                    f"no executor for command (default deny): {job.command!r}"
                )
            plan = (
                self._execution_verifier(job)
                if job.command == "pr" and job.approved_by is not None
                else None
            )
            outcome = executor(job)
            if plan is not None:
                self._postcondition_verifier(job, outcome, plan)
        except Exception as exc:  # noqa: BLE001 — 실행 실패를 FAILED 로 기록(루프 생존)
            return self._fail(job, started, exc)

        duration_ms = self._duration_ms(started)
        # 출력 게이트(주입 방어 3계층): diff 가 있는 L1 쓰기는 사람 승인 전에
        # 멈춘다. 이미 승인된 job(approved_by 기록)은 게이트를 재통과하지 않는다.
        # 게이트를 거치는 job(pr)은 prepare/execute 각 1회씩 metric 이 2건 기록된다 —
        # 실행(Claude 호출)이 실제로 2회이므로 의도된 동작(대시보드는 job 단위 집계).
        if outcome.diff is not None and job.approved_by is None:
            if job.command != "pr":
                return self._fail(
                    job,
                    started,
                    ExecutionPlanError("write output gate is only defined for PR execution plans"),
                )
            try:
                plan = self._plan_builder(job, outcome.diff)
            except Exception as exc:  # noqa: BLE001 — unsafe plan must fail closed
                return self._fail(job, started, exc)
            updated = self._jobs.await_approval(
                job.id,
                outcome.diff,
                execution_plan=plan.canonical_json(),
                execution_plan_hash=plan.digest(),
            )
            self._audit.append(
                job.id,
                AUDIT_AWAITING_APPROVAL,
                actor=WORKER_ACTOR,
                detail=f"diff {len(outcome.diff)} chars; plan={plan.digest()}",
                context={
                    "execution_plan_hash": plan.digest(),
                    "policy_version": plan.policy_version,
                },
            )
            self._record(job, duration_ms, outcome, success=True)
            return updated

        if job.command == "pr" and job.approved_by is not None:
            self._audit.append(
                job.id,
                AUDIT_POSTCONDITION_VERIFIED,
                actor=WORKER_ACTOR,
                detail=f"approval_hash={job.approval_hash}",
                context={
                    "approval_hash": job.approval_hash or "",
                    "check": "remote_pr_diff",
                },
            )
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


def stores_from_env() -> tuple[JobStore, AuditStore, TelemetryStore]:
    """환경에서 job/audit/telemetry store 3종을 같은 DynamoDB(단일테이블)로 구성.

    DDB_ENDPOINT 있으면 DynamoDB Local, 없으면 실 DynamoDB. 대시보드(web/)가 읽는
    같은 `slackops-agent` 테이블을 공유한다 — worker 의 전이/audit/metric 이 라이브로
    노출된다. boto3 는 lazy import(미설치 환경 import-safe).
    """
    import boto3  # lazy: 선택 의존성

    table = os.environ.get("DDB_TABLE", "slackops-agent")
    endpoint = os.environ.get("DDB_ENDPOINT")
    region = os.environ.get("AWS_REGION", "us-east-1")
    kwargs: dict[str, Any] = {"region_name": region}
    if endpoint:
        kwargs["endpoint_url"] = endpoint
    dynamodb = boto3.resource("dynamodb", **kwargs)

    from app.store import (
        DynamoDbAuditStore,
        DynamoDbJobStore,
        DynamoDbTelemetryStore,
    )

    return (
        DynamoDbJobStore(table, dynamodb=dynamodb),
        DynamoDbAuditStore(table, dynamodb=dynamodb),
        DynamoDbTelemetryStore(table, dynamodb=dynamodb),
    )


def main() -> None:
    """CLI — 공유 큐 폴링 worker. `python -m app.worker`.

    DDB_ENDPOINT 로 DynamoDB Local↔실 DynamoDB 전환. 명령 실행은 실 Claude Code
    Headless(runner 미주입 = 기본 SubprocessRunner) — `CLAUDE_CODE_OAUTH_TOKEN` +
    claude CLI 필요. 승인된 job(APPROVED)을 우선 재claim 해 출력 게이트 이후 execute
    단계를 이어가고, 신규 PENDING 은 L0 즉시 / L1 은 게이트(AWAITING_APPROVAL)로 멈춘다.
    """
    import structlog  # lazy

    parser = argparse.ArgumentParser(
        description="SlackOps EC2 Agent Worker (공유 큐 consumer)"
    )
    parser.add_argument(
        "--once", action="store_true", help="claim 가능한 job 1건만 처리하고 종료"
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=None,
        help="폴링 횟수 상한(기본 무한 — 운영 모드)",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=POLL_INTERVAL_S,
        help="큐가 비었을 때 대기 간격(초)",
    )
    args = parser.parse_args()

    log = structlog.get_logger()
    job_store, audit_store, telemetry_store = stores_from_env()
    worker = Worker(job_store, audit_store, telemetry_store)  # runner=None → 실 claude

    if args.once:
        job = worker.process_one()
        if job is None:
            log.info("worker.idle")
        else:
            log.info(
                "worker.processed",
                job_id=job.id,
                command=job.command,
                status=job.status.value,
            )
        return

    log.info(
        "worker.run_forever",
        poll_interval_s=args.poll_interval,
        max_iterations=args.max_iterations,
    )
    processed = worker.run_forever(
        poll_interval_s=args.poll_interval, max_iterations=args.max_iterations
    )
    log.info("worker.stopped", processed=processed)


if __name__ == "__main__":
    main()
