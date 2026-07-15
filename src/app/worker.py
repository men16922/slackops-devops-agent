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
import base64
import binascii
import os
import time
from collections.abc import Generator
from contextlib import AbstractContextManager, contextmanager, nullcontext
from dataclasses import dataclass
from typing import Any, Callable

from app.claude_runner import SubprocessRunner, ToolCall
from app.execution_plan import (
    ExecutionPlan,
    ExecutionPlanError,
    build_pr_plan,
    verify_pr_workspace,
    verify_remote_pr_diff,
)
from app.policy_boundary import CommandScope, PolicyDenied, authorize_command
from app.store import (
    AuditStore,
    Job,
    JobStatus,
    JobStore,
    TelemetryStore,
    result_digest,
)
from app.telemetry import RunMetrics, record_run_metrics
from app.write_credentials import (
    GitHubAppGrantIssuer,
    GrantIssuer,
    WriteGrant,
    pr_write_grant,
)

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
AUDIT_PLAN_BINDING_REJECTED = "plan_binding_rejected"
AUDIT_POLICY_DENIED = "policy_denied"
AUDIT_WRITE_CREDENTIALS_ISSUED = "write_credentials_issued"
AUDIT_TOOL_CALL = "tool_call"
AUDIT_CAPABILITY_DRIFT = "capability_drift"

# 해석되지 않은 도구는 지우지 않고 이 접두사로 드러낸다.
_UNRESOLVED_PREFIX = "unresolved:"


class CapabilityDrift(Exception):
    """실제로 관측된 capability 가 인가된 범위를 벗어났다."""

    def __init__(self, reason: str, *, observed: tuple[str, ...] = ()) -> None:
        super().__init__(f"capability drift: {reason}")
        self.reason = reason
        self.observed = observed

# 승인된 PR execute 단계가 push 할 저장소(owner/name). 미설정이면 write credential 을
# 발급하지 않는다 — 자격 없이 실행되어 push 가 실패한다(fail closed, 로컬/데모 기본값).
PR_REPOSITORY_ENV = "SLACKOPS_PR_REPOSITORY"
_GITHUB_APP_ID_ENV = "SLACKOPS_GITHUB_APP_ID"
_GITHUB_INSTALLATION_ID_ENV = "SLACKOPS_GITHUB_INSTALLATION_ID"
# PEM 은 여러 줄이라 systemd EnvironmentFile 로 그대로 전달할 수 없다 — base64 로 받는다.
_GITHUB_PRIVATE_KEY_ENV = "SLACKOPS_GITHUB_APP_PRIVATE_KEY_B64"


@dataclass
class CommandOutcome:
    """명령 실행기 1회 실행의 결과.

    Attributes:
        result: 사용자에게 게시할 결과 텍스트.
        diff: L1 쓰기의 변경 diff. None 이 아니고 job 이 아직 미승인이면
            출력 게이트(AWAITING_APPROVAL)로 분기한다.
        tokens / cost_usd / tool_calls: 계측 메타(없으면 None).
        tool_steps: 이 실행에서 **관측된** 도구 호출. 감사 궤적의 자식 스텝이 되고,
            capability 를 정적 allowlist 가 아니라 실제 사용으로 재집계하는 근거가 된다.
    """

    result: str = ""
    diff: str | None = None
    tokens: int | None = None
    cost_usd: float | None = None
    tool_calls: int | None = None
    tool_steps: tuple[ToolCall, ...] = ()


# 명령 실행기 시그니처: (job) → CommandOutcome. 예외는 worker 가 FAILED 로 기록한다.
CommandExecutor = Callable[[Job], CommandOutcome]
PlanBuilder = Callable[[Job, str], ExecutionPlan]
ExecutionVerifier = Callable[[Job], ExecutionPlan]
PostconditionVerifier = Callable[[Job, CommandOutcome, ExecutionPlan], None]
ScopeAuthorizer = Callable[[str, str], CommandScope]
# (job, 재검증된 plan) → write credential 을 그 단계 동안만 여는 컨텍스트.
# 컨텍스트를 벗어나면 자격은 회수된다. 미구성 환경은 None 을 내보낸다(fail closed).
GrantProvider = Callable[[Job, ExecutionPlan], AbstractContextManager[WriteGrant | None]]


def grant_issuer_from_env() -> tuple[str, GrantIssuer] | None:
    """환경이 완전히 구성된 경우에만 (repository, issuer) 를 반환한다.

    부분 구성은 조용히 비활성화하지 않고 실패시킨다 — "설정한 줄 알았는데 자격이 없어
    push 가 실패" 하는 상태와 "의도적으로 미구성" 을 구분한다.
    """
    repository = os.environ.get(PR_REPOSITORY_ENV, "").strip()
    app_id = os.environ.get(_GITHUB_APP_ID_ENV, "").strip()
    installation_id = os.environ.get(_GITHUB_INSTALLATION_ID_ENV, "").strip()
    private_key_b64 = os.environ.get(_GITHUB_PRIVATE_KEY_ENV, "").strip()
    configured = [repository, app_id, installation_id, private_key_b64]
    if not any(configured):
        return None
    if not all(configured):
        raise ValueError(
            "write credential configuration is incomplete: "
            f"{PR_REPOSITORY_ENV}/{_GITHUB_APP_ID_ENV}/{_GITHUB_INSTALLATION_ID_ENV}/"
            f"{_GITHUB_PRIVATE_KEY_ENV} must all be set together"
        )
    try:
        private_key = base64.b64decode(private_key_b64, validate=True).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError) as exc:
        raise ValueError(f"{_GITHUB_PRIVATE_KEY_ENV} is not valid base64 PEM: {exc}") from None
    return repository, GitHubAppGrantIssuer(app_id, installation_id, private_key)


def _env_grant_provider(
    job: Job, plan: ExecutionPlan
) -> AbstractContextManager[WriteGrant | None]:
    configured = grant_issuer_from_env()
    if configured is None:
        return nullcontext(None)
    repository, issuer = configured
    return pr_write_grant(job, plan, repository=repository, issuer=issuer)


def _build_pr_plan(job: Job, diff: str) -> ExecutionPlan:
    scope = authorize_command("pr")
    return build_pr_plan(
        job.args,
        diff,
        execution_tools=_pr_execution_tools(),
        account_id=scope.account_id,
        region=scope.region,
    )


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
    scope = authorize_command("pr")
    return verify_pr_workspace(
        job.args,
        job.diff,
        job.execution_plan,
        job.execution_plan_hash,
        expected_execution_tools=_pr_execution_tools(),
        account_id=scope.account_id,
        region=scope.region,
    )


def _verify_pr_postcondition(
    _job: Job, outcome: CommandOutcome, plan: ExecutionPlan
) -> None:
    verify_remote_pr_diff(outcome.result, plan)


def default_executors(
    runner: SubprocessRunner | None = None,
    *,
    grant_provider: GrantProvider | None = None,
) -> dict[str, CommandExecutor]:
    """permissions 레지스트리의 MVP 명령에 대한 기본 실행기 매핑 생성.

    핸들러는 호출 시점에 모듈 속성으로 조회한다(slack_handler 와 동일 패턴 —
    테스트에서 monkeypatch 주입 가능). pr 은 PrResult.diff 를 CommandOutcome.diff
    로 연결해 출력 게이트(AWAITING_APPROVAL)로 분기시킨다.

    Args:
        runner: claude-backed 핸들러에 전달할 subprocess 실행기(테스트 주입점).
        grant_provider: 승인된 pr execute 단계에만 단기 write credential 을 여는 컨텍스트
            제공자. None 이면 자격 없이 실행된다(로컬/데모 — push 는 실패).
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
            # pr 은 prepare/execute 로 Claude 를 2회 호출한다 — 궤적은 두 호출의 도구를
            # 모두 담아야 하므로 마지막 것만 취하지 않는다.
            steps: list[ToolCall] = []
            for metrics in captured:
                steps.extend(metrics.tool_calls)
            outcome.tool_steps = tuple(steps)
            outcome.tool_calls = len(steps) or None
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
        # prepare 단계에는 grant 컨텍스트 자체가 열리지 않는다 — 자격이 없으니 push 도 없다.
        if approved_diff is None or grant_provider is None:
            pr_result = pr.handle_pr(
                job.args,
                approved_diff=approved_diff,
                runner=runner,
                on_metrics=captured.append,
            )
            return _merge_metrics(
                CommandOutcome(result=pr_result.summary, diff=pr_result.diff), captured
            )
        # 승인 plan 을 실 workspace 에 대해 다시 검증한 **직후**에 자격을 발급한다.
        # 검증과 발급 사이에 창이 없어야 승인된 것과 실행되는 것이 갈라지지 않는다.
        plan = _verify_approved_pr(job)
        with grant_provider(job, plan) as grant:
            pr_result = pr.handle_pr(
                job.args,
                approved_diff=approved_diff,
                runner=runner,
                on_metrics=captured.append,
                write_grant=grant,
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
        scope_authorizer: ScopeAuthorizer | None = None,
        grant_provider: GrantProvider | None = None,
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
            scope_authorizer: executor 전에 account/region/resource/time-window scope를
                결정적으로 검증하는 함수. None 이면 production environment policy 사용.
            grant_provider: 승인된 pr execute 단계의 단기 write credential 제공자.
                None 이면 환경 구성(SLACKOPS_PR_REPOSITORY + GitHub App)에서 유도한다.
        """
        self._jobs = job_store
        self._audit = audit_store
        self._metrics = telemetry_store
        self._grant_provider = (
            grant_provider if grant_provider is not None else _env_grant_provider
        )
        self._executors = (
            executors
            if executors is not None
            else default_executors(runner, grant_provider=self._audited_grant)
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
        self._scope_authorizer = (
            scope_authorizer if scope_authorizer is not None else authorize_command
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
        # The claim is this job's root step; every later step descends from it, so the
        # trail reads as one trajectory rather than a flat list of transitions.
        claimed = self._audit.append(
            job.id,
            AUDIT_CLAIMED,
            actor=WORKER_ACTOR,
            detail=f"command={job.command}",
            context={"command": job.command},
            tool_name=job.command,
        )
        root_step = claimed.step_id
        target_resource = ""

        started = self._monotonic()
        executor = self._executors.get(job.command)
        resolved: tuple[tuple[ToolCall, str], ...] = ()
        observed: tuple[str, ...] = ()
        try:
            if executor is None:
                raise LookupError(
                    f"no executor for command (default deny): {job.command!r}"
                )
            # Custom executors are also behind this gate, so a future handler
            # cannot bypass the adapter-level scope check by worker wiring.
            target_resource = self._scope_authorizer(job.command, job.args).resource
            plan = (
                self._execution_verifier(job)
                if job.command == "pr" and job.approved_by is not None
                else None
            )
            outcome = executor(job)
            # What was permitted and what ran are different claims. Check the second
            # one before the result is allowed to count as a completed job.
            resolved = self._resolve_tool_steps(job, outcome)
            observed = self._enforce_observed_capability(job, resolved, plan)
            if plan is not None:
                self._postcondition_verifier(job, outcome, plan)
        except Exception as exc:  # noqa: BLE001 — 실행 실패를 FAILED 로 기록(루프 생존)
            return self._fail(job, started, exc, root_step, target_resource, resolved)

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
                    root_step,
                    target_resource,
                )
            try:
                plan = self._plan_builder(job, outcome.diff)
            except Exception as exc:  # noqa: BLE001 — unsafe plan must fail closed
                return self._fail(job, started, exc, root_step, target_resource)
            updated = self._jobs.await_approval(
                job.id,
                outcome.diff,
                execution_plan=plan.canonical_json(),
                execution_plan_hash=plan.digest(),
            )
            self._record_tool_steps(job, root_step, resolved)
            self._audit.append(
                job.id,
                AUDIT_AWAITING_APPROVAL,
                actor=WORKER_ACTOR,
                detail=f"diff {len(outcome.diff)} chars; plan={plan.digest()}",
                context={
                    "execution_plan_hash": plan.digest(),
                    "policy_version": plan.policy_version,
                    "risk_score": str(plan.risk_score),
                    "risk_ceiling": str(plan.risk_ceiling),
                    # 승인자가 보는 것은 계획이지만, 남는 것은 실제로 무엇이 돌았는지다.
                    "observed_capabilities": ",".join(observed),
                },
                parent_step_id=root_step,
                tool_name=job.command,
                capabilities=plan.capabilities,
                target_resource=target_resource,
                # The gate holds the diff, so hash it here: an approver's decision and
                # the artifact they saw stay linked even if the body is later trimmed.
                result_hash=result_digest(outcome.diff),
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
                parent_step_id=root_step,
                tool_name="gh pr diff",
                target_resource=target_resource,
            )
        self._record_tool_steps(job, root_step, resolved)
        updated = self._jobs.complete(
            job.id,
            status=JobStatus.DONE,
            result=outcome.result,
            cost_usd=outcome.cost_usd,
            tokens=outcome.tokens,
        )
        self._audit.append(
            job.id,
            AUDIT_DONE,
            actor=WORKER_ACTOR,
            parent_step_id=root_step,
            tool_name=job.command,
            capabilities=observed,
            target_resource=target_resource,
            result_hash=result_digest(outcome.result),
        )
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
    def _resolve_tool_steps(
        self, job: Job, outcome: CommandOutcome
    ) -> tuple[tuple[ToolCall, str], ...]:
        """관측된 각 호출을 그것을 인가한 allowlist 도구 패턴으로 해석한다.

        guard 의 파스를 재사용한다 — 실행을 실제로 허가하는 것과 의견이 갈릴 수 있는
        분류기를 하나 더 두지 않는다.
        """
        from app.command_guard import CommandGuardError, resolve_tool

        resolved: list[tuple[ToolCall, str]] = []
        for call in outcome.tool_steps:
            tool = call.name
            if call.command:
                try:
                    tool = resolve_tool(job.command, call.command)
                except CommandGuardError:
                    # guard 가 허용한 것만 실행됐어야 한다. 해석되지 않는 명령줄은
                    # 감사에서 지우지 말고 있는 그대로 남긴다.
                    tool = f"{_UNRESOLVED_PREFIX}{call.name}"
            resolved.append((call, tool))
        return tuple(resolved)

    def _observed_capabilities(
        self, resolved: tuple[tuple[ToolCall, str], ...]
    ) -> tuple[str, ...]:
        from app.execution_plan import capabilities_for_tools

        tools = tuple(
            sorted({t for _c, t in resolved if not t.startswith(_UNRESOLVED_PREFIX)})
        )
        try:
            return capabilities_for_tools(tools)
        except ExecutionPlanError:
            return ()

    def _enforce_observed_capability(
        self,
        job: Job,
        resolved: tuple[tuple[ToolCall, str], ...],
        plan: ExecutionPlan | None,
    ) -> tuple[str, ...]:
        """관측된 capability 가 인가된 범위를 넘으면 실행을 실패시킨다.

        정상 경로에서는 guard 가 argv 단계에서 이미 막으므로 이 검사는 조용하다. 그것이
        요점이다 — guard 가 우회되거나 도구 표면이 드리프트하면, 그 사실이 감사 기록이
        아니라 **거부**로 드러나야 한다. 승인 시점 capability 가 기준이며, 정적 allowlist 는
        승인 계획이 없는 명령의 상한이다.

        Raises:
            CapabilityDrift: 관측 capability/risk 가 인가 범위를 초과.
        """
        from app.execution_plan import capabilities_for_tools, risk_score

        observed = self._observed_capabilities(resolved)
        unresolved = [c.command or c.name for c, t in resolved if t.startswith(_UNRESOLVED_PREFIX)]
        if unresolved:
            raise CapabilityDrift(
                f"observed a tool call the guard does not authorize: {unresolved[0]!r}",
                observed=observed,
            )
        if not observed:
            return observed
        if plan is not None:
            authorized = tuple(plan.capabilities)
            ceiling = plan.risk_score
        else:
            try:
                from app.allowlist import allowed_tools

                authorized = capabilities_for_tools(tuple(sorted(allowed_tools(job.command))))
            except Exception:  # noqa: BLE001 — allowlist 없는 명령(ping)은 도구도 없다
                authorized = ()
            ceiling = risk_score(authorized) if authorized else 0
        extra = set(observed) - set(authorized)
        if extra:
            raise CapabilityDrift(
                f"observed capability outside the authorized set: {sorted(extra)}",
                observed=observed,
            )
        score = risk_score(observed)
        if score > ceiling:
            raise CapabilityDrift(
                f"observed risk {score} exceeds the authorized {ceiling}", observed=observed
            )
        return observed

    def _record_tool_steps(
        self, job: Job, parent_step_id: str, resolved: tuple[tuple[ToolCall, str], ...]
    ) -> None:
        """관측된 도구 호출을 Claude 호출 아래 자식 스텝으로 남긴다."""
        for call, tool in resolved:
            self._audit.append(
                job.id,
                AUDIT_TOOL_CALL,
                actor=WORKER_ACTOR,
                detail=call.command or call.name,
                context={"tool_use_id": call.tool_use_id, "is_error": str(call.is_error)},
                parent_step_id=parent_step_id,
                tool_name=tool,
                target_resource=job.args,
                result_hash=call.result_hash,
            )

    @contextmanager
    def _audited_grant(
        self, job: Job, plan: ExecutionPlan
    ) -> Generator[WriteGrant | None]:
        """write credential 발급을 감사에 남긴다 — 토큰 자체는 절대 기록하지 않는다.

        실 push 를 그것을 허가한 승인(jobId/approvalHash/policyVersion)으로 되짚을 수
        있게 하는 연결고리다.
        """
        with self._grant_provider(job, plan) as grant:
            if grant is not None:
                # Parent = the approval step this credential answers to, so a real push
                # can be walked back to the decision that authorized it.
                approval_step = self._approval_step_id(job.id)
                self._audit.append(
                    job.id,
                    AUDIT_WRITE_CREDENTIALS_ISSUED,
                    actor=WORKER_ACTOR,
                    detail=f"scoped write credential for {grant.repository}",
                    context=grant.audit_context(),
                    parent_step_id=approval_step,
                    tool_name="sts:github-app-installation-token",
                    capabilities=plan.capabilities,
                    target_resource=f"repo:{grant.repository}",
                )
            yield grant

    def _approval_step_id(self, job_id: str) -> str:
        """The step where a human approved this job, if the trail records one."""
        from app.approval_actions import AUDIT_APPROVED  # lazy: avoids an import cycle

        for event in reversed(self._audit.list_for_job(job_id)):
            if event.action in (AUDIT_APPROVED, AUDIT_AWAITING_APPROVAL) and event.step_id:
                return event.step_id
        return ""

    def _duration_ms(self, started: float) -> float:
        return (self._monotonic() - started) * 1000.0

    def _fail(
        self,
        job: Job,
        started: float,
        exc: Exception,
        root_step: str = "",
        target_resource: str = "",
        resolved: tuple[tuple[ToolCall, str], ...] = (),
    ) -> Job | None:
        error = f"{type(exc).__name__}: {exc}"
        updated = self._jobs.complete(job.id, status=JobStatus.FAILED, error=error)
        # 실패해도 실제로 무엇이 돌았는지는 남긴다 — 궤적에 구멍이 생기면 안 된다.
        self._record_tool_steps(job, root_step, resolved)
        if isinstance(exc, CapabilityDrift):
            self._audit.append(
                job.id,
                AUDIT_CAPABILITY_DRIFT,
                actor=WORKER_ACTOR,
                detail="observed capability exceeded the authorized set",
                context={"reason": exc.reason, "observed": ",".join(exc.observed)},
                parent_step_id=root_step,
                tool_name=job.command,
                capabilities=exc.observed,
                target_resource=target_resource,
            )
        elif isinstance(exc, ExecutionPlanError):
            self._audit.append(
                job.id,
                AUDIT_PLAN_BINDING_REJECTED,
                actor=WORKER_ACTOR,
                detail="execution plan verification failed",
                context={"error_type": type(exc).__name__, "reason": str(exc)},
                parent_step_id=root_step,
                tool_name=job.command,
                target_resource=target_resource,
            )
        elif isinstance(exc, LookupError):
            self._audit.append(
                job.id,
                AUDIT_POLICY_DENIED,
                actor=WORKER_ACTOR,
                detail="command rejected by default-deny executor gate",
                context={"command": job.command, "reason": "default_deny"},
                parent_step_id=root_step,
                tool_name=job.command,
            )
        elif isinstance(exc, PolicyDenied):
            context = exc.scope.audit_context()
            context["reason"] = exc.reason
            self._audit.append(
                job.id,
                AUDIT_POLICY_DENIED,
                actor=WORKER_ACTOR,
                detail="command rejected by deterministic scope boundary",
                context=context,
                parent_step_id=root_step,
                tool_name=job.command,
                target_resource=exc.scope.resource,
            )
        self._audit.append(
            job.id,
            AUDIT_FAILED,
            actor=WORKER_ACTOR,
            detail=error,
            parent_step_id=root_step,
            tool_name=job.command,
            target_resource=target_resource,
        )
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
