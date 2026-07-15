"""worker 폴링 루프 테스트 — SqliteJobStore + mock 으로 claim→실행→전이 e2e.

실 AWS/Claude/subprocess 호출 없음: runner/fetcher/executors/monotonic/sleep 전부 주입.
"""

from __future__ import annotations

import pytest

from app.commands import logs
from app.execution_plan import ExecutionPlan, ExecutionPlanError
from app.store import (
    Job,
    JobSource,
    JobStatus,
    SqliteAuditStore,
    SqliteJobStore,
    SqliteTelemetryStore,
)
from app.worker import (
    AUDIT_AWAITING_APPROVAL,
    AUDIT_CLAIMED,
    AUDIT_DONE,
    AUDIT_FAILED,
    AUDIT_POSTCONDITION_VERIFIED,
    AUDIT_PLAN_BINDING_REJECTED,
    AUDIT_POLICY_DENIED,
    WORKER_ACTOR,
    CommandOutcome,
    Worker,
    default_executors,
)
from tests._helpers import (
    RecordingFetcher,
    RecordingRunner,
    counter_clock,
    counter_id,
    result_json,
)


@pytest.fixture()
def stores() -> tuple[SqliteJobStore, SqliteAuditStore, SqliteTelemetryStore]:
    return (
        SqliteJobStore(clock=counter_clock(), id_factory=counter_id()),
        SqliteAuditStore(clock=counter_clock()),
        SqliteTelemetryStore(clock=counter_clock()),
    )


def make_worker(
    stores: tuple[SqliteJobStore, SqliteAuditStore, SqliteTelemetryStore],
    **kwargs: object,
) -> Worker:
    jobs, audit, metrics = stores
    # Worker unit tests exercise state transitions with fake executors, not a
    # real git worktree. Production uses the strict default validators.
    kwargs.setdefault(
        "plan_builder",
        lambda job, diff: ExecutionPlan(
            command="pr",
            args_sha256="test-args",
            diff_sha256="test-diff",
            paths=("x.py",),
            policy_version="secure-runtime-v1",
            workspace_root="/test/workspace",
        ),
    )
    kwargs.setdefault(
        "execution_verifier",
        lambda _job: ExecutionPlan(
            command="pr",
            args_sha256="test-args",
            diff_sha256="test-diff",
            paths=("x.py",),
            policy_version="secure-runtime-v1",
            workspace_root="/test/workspace",
        ),
    )
    kwargs.setdefault("postcondition_verifier", lambda _job, _outcome, _plan: None)
    return Worker(jobs, audit, metrics, **kwargs)  # type: ignore[arg-type]


def fake_monotonic(values: list[float]):
    """주입용 단조 시계 — 호출마다 values 를 순서대로 반환."""
    it = iter(values)
    return lambda: next(it)


# ── 빈 큐 / 폴링 루프 ─────────────────────────────────────────


def test_process_one_returns_none_on_empty_queue(stores) -> None:
    worker = make_worker(stores, executors={})
    assert worker.process_one() is None


def test_run_forever_sleeps_when_empty_and_processes_jobs(stores) -> None:
    jobs, _, _ = stores
    jobs.enqueue("noop", source=JobSource.WEB)
    jobs.enqueue("noop", source=JobSource.WEB)
    sleeps: list[float] = []
    worker = make_worker(
        stores, executors={"noop": lambda _job: CommandOutcome(result="ok")}
    )
    processed = worker.run_forever(
        poll_interval_s=0.5, max_iterations=3, sleep=sleeps.append
    )
    assert processed == 2
    assert sleeps == [0.5]  # 마지막 1회는 빈 큐 → sleep


# ── claim→실행→complete e2e (mock runner + SqliteJobStore) ────


def test_logs_job_e2e_done_with_audit_and_metric(stores) -> None:
    jobs, audit, metrics = stores
    runner = RecordingRunner(stdout=result_json("로그 분석 결과"))
    fetcher = RecordingFetcher("ERROR boom")

    def logs_executor(job: Job) -> CommandOutcome:
        return CommandOutcome(
            result=logs.handle_logs(job.args, fetcher=fetcher, runner=runner)
        )

    job = jobs.enqueue(
        "logs", "payments-api", source=JobSource.SLACK, requested_by="U1", channel="C1"
    )
    worker = make_worker(stores, executors={"logs": logs_executor})

    done = worker.process_one()

    assert done is not None
    assert done.id == job.id
    assert done.status is JobStatus.DONE
    assert done.result == "로그 분석 결과"
    assert fetcher.calls == ["payments-api"]
    assert len(runner.calls) == 1  # mock runner 경유 — 실 subprocess 없음

    actions = [e.action for e in audit.list_for_job(job.id)]
    assert actions == [AUDIT_CLAIMED, AUDIT_DONE]
    assert all(e.actor == WORKER_ACTOR for e in audit.list_for_job(job.id))

    recorded = metrics.list_for_job(job.id)
    assert len(recorded) == 1
    assert recorded[0].command == "logs"
    assert recorded[0].success is True


def test_ping_job_with_default_executors(stores) -> None:
    jobs, _, _ = stores
    job = jobs.enqueue("ping", source=JobSource.WEB)
    worker = make_worker(stores, executors=default_executors())

    done = worker.process_one()

    assert done is not None and done.id == job.id
    assert done.status is JobStatus.DONE
    assert done.result is not None and "pong" in done.result


def test_duration_ms_recorded_from_injected_monotonic(stores) -> None:
    jobs, _, metrics = stores
    job = jobs.enqueue("noop", source=JobSource.WEB)
    worker = make_worker(
        stores,
        executors={"noop": lambda _job: CommandOutcome(result="ok")},
        monotonic=fake_monotonic([10.0, 10.5]),
    )
    worker.process_one()
    recorded = metrics.list_for_job(job.id)
    assert recorded[0].duration_ms == pytest.approx(500.0)


# ── 출력 게이트(pr) 분기 ──────────────────────────────────────


def test_pr_outcome_with_diff_stops_at_awaiting_approval(stores) -> None:
    jobs, audit, metrics = stores
    job = jobs.enqueue("pr", "fix typo", source=JobSource.SLACK, requested_by="U1")
    diff = "--- a/x.py\n+++ b/x.py\n-old\n+new"
    worker = make_worker(
        stores,
        executors={"pr": lambda _job: CommandOutcome(result="PR 준비됨", diff=diff)},
    )

    gated = worker.process_one()

    assert gated is not None
    assert gated.status is JobStatus.AWAITING_APPROVAL
    assert gated.diff == diff
    actions = [e.action for e in audit.list_for_job(job.id)]
    assert actions == [AUDIT_CLAIMED, AUDIT_AWAITING_APPROVAL]
    # 게이트 도달도 실행 1건으로 계측된다.
    assert metrics.list_for_job(job.id)[0].success is True


def test_approved_pr_job_completes_without_regating(stores) -> None:
    jobs, audit, _ = stores
    job = jobs.enqueue("pr", "fix typo", source=JobSource.SLACK, requested_by="U1")
    diff = "--- a/x.py\n+++ b/x.py"
    worker = make_worker(
        stores,
        executors={
            "pr": lambda _job: CommandOutcome(result="PR created: #42", diff=diff)
        },
    )

    assert worker.process_one().status is JobStatus.AWAITING_APPROVAL  # type: ignore[union-attr]
    assert jobs.approve(job.id, "alice") is not None

    done = worker.process_one()  # APPROVED 가 재claim — diff 가 있어도 게이트 재진입 없음

    assert done is not None
    assert done.status is JobStatus.DONE
    assert done.result == "PR created: #42"
    assert done.approved_by == "alice"
    actions = [e.action for e in audit.list_for_job(job.id)]
    assert actions == [
        AUDIT_CLAIMED,
        AUDIT_AWAITING_APPROVAL,
        AUDIT_CLAIMED,
        AUDIT_POSTCONDITION_VERIFIED,
        AUDIT_DONE,
    ]


def test_pr_default_executor_gates_then_creates_pr_after_approval(stores) -> None:
    """default_executors 의 pr 경로 e2e — prepare 게이트 → 승인 → execute 완료.

    1차(prepare) argv 에는 push/PR 도구가 없고(게이트 없이 PR 생성 불가),
    승인 후 2차(execute) argv 에만 push/PR 도구가 들어간다.
    """
    from app.commands.pr import DIFF_BEGIN_MARKER, DIFF_END_MARKER

    diff = "--- a/x.py\n+++ b/x.py\n-old\n+new"
    runner = RecordingRunner(
        stdout=result_json(f"준비 완료\n{DIFF_BEGIN_MARKER}\n{diff}\n{DIFF_END_MARKER}")
    )
    jobs, _, _ = stores
    job = jobs.enqueue("pr", "fix typo", source=JobSource.SLACK, requested_by="U1")
    worker = make_worker(stores, executors=default_executors(runner=runner))

    gated = worker.process_one()

    assert gated is not None
    assert gated.status is JobStatus.AWAITING_APPROVAL
    assert gated.diff == diff
    first_cmd, _ = runner.calls[0]
    assert "Bash(gh pr create:*)" not in first_cmd
    assert "Bash(git push:*)" not in first_cmd

    assert jobs.approve(job.id, "alice") is not None
    done = worker.process_one()

    assert done is not None
    assert done.status is JobStatus.DONE
    second_cmd, _ = runner.calls[1]
    assert "Bash(gh pr create:*)" in second_cmd
    assert "Bash(git push:*)" in second_cmd


def test_tf_review_executor_e2e_done(stores) -> None:
    jobs, _, _ = stores
    from app.commands import tf_review

    job = jobs.enqueue("tf-review", source=JobSource.WEB)
    runner = RecordingRunner(stdout=result_json("plan 리뷰 결과"))

    def tf_executor(_job: Job) -> CommandOutcome:
        return CommandOutcome(
            result=tf_review.handle_tf_review(
                fetcher=lambda: "Plan: 1 to add", runner=runner
            )
        )

    worker = make_worker(stores, executors={"tf-review": tf_executor})
    done = worker.process_one()

    assert done is not None and done.id == job.id
    assert done.status is JobStatus.DONE
    assert done.result == "plan 리뷰 결과"


# ── 실패 경로 ─────────────────────────────────────────────────


def test_executor_exception_marks_failed_with_audit_and_metric(stores) -> None:
    jobs, audit, metrics = stores
    job = jobs.enqueue("logs", "svc", source=JobSource.SLACK)

    def boom(_job: Job) -> CommandOutcome:
        raise RuntimeError("fetch exploded")

    worker = make_worker(stores, executors={"logs": boom})

    failed = worker.process_one()

    assert failed is not None
    assert failed.status is JobStatus.FAILED
    assert failed.error is not None and "fetch exploded" in failed.error
    actions = [e.action for e in audit.list_for_job(job.id)]
    assert actions == [AUDIT_CLAIMED, AUDIT_FAILED]
    recorded = metrics.list_for_job(job.id)
    assert recorded[0].success is False
    assert recorded[0].error is not None and "fetch exploded" in recorded[0].error


def test_unknown_command_fails_without_execution(stores) -> None:
    jobs, audit, _ = stores
    job = jobs.enqueue("rm-rf", source=JobSource.WEB)
    worker = make_worker(stores, executors={})

    failed = worker.process_one()

    assert failed is not None
    assert failed.status is JobStatus.FAILED
    assert failed.error is not None and "default deny" in failed.error
    assert [event.action for event in audit.list_for_job(job.id)] == [
        AUDIT_CLAIMED,
        AUDIT_POLICY_DENIED,
        AUDIT_FAILED,
    ]


def test_plan_binding_failure_records_dedicated_security_event(stores) -> None:
    jobs, audit, _ = stores
    job = jobs.enqueue("pr", "fix typo", source=JobSource.WEB)
    worker = make_worker(
        stores,
        executors={"pr": lambda _job: CommandOutcome(result="prepared", diff="--- a/x\n+++ b/x")},
        plan_builder=lambda _job, _diff: (_ for _ in ()).throw(ExecutionPlanError("diff changed")),
    )

    failed = worker.process_one()

    assert failed is not None and failed.status is JobStatus.FAILED
    events = audit.list_for_job(job.id)
    assert [event.action for event in events] == [
        AUDIT_CLAIMED,
        AUDIT_PLAN_BINDING_REJECTED,
        AUDIT_FAILED,
    ]
    assert events[1].context == {"error_type": "ExecutionPlanError"}


# ── telemetry 계측 결합 (on_metrics → CommandOutcome → metric) ───


def test_default_executors_metric_carries_real_cost(
    stores, monkeypatch: pytest.MonkeyPatch
) -> None:
    """run_for_command 가 emit 한 호출 계측(cost)이 metric write-back 까지 흐른다."""
    jobs, _, metrics = stores
    monkeypatch.setattr(logs, "fetch_cloudwatch_logs", RecordingFetcher("ERROR boom"))
    runner = RecordingRunner(stdout=result_json("분석 결과", cost=0.05))

    job = jobs.enqueue("logs", "payments-api", source=JobSource.SLACK)
    worker = make_worker(stores, executors=default_executors(runner))
    done = worker.process_one()

    assert done is not None and done.status is JobStatus.DONE
    assert done.cost_usd == 0.05  # complete() 에도 실 cost 가 실린다
    [recorded] = metrics.list_for_job(job.id)
    assert recorded.cost_usd == 0.05


def test_worker_tracer_emits_otel_span(stores) -> None:
    """tracer 주입 시 metric write-back 이 OTel span 으로도 emit 된다."""
    pytest.importorskip("opentelemetry.sdk")
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
        InMemorySpanExporter,
    )

    from app.telemetry import setup_telemetry

    exporter = InMemorySpanExporter()
    tracer = setup_telemetry(span_exporter=exporter)
    jobs, _, _ = stores
    jobs.enqueue("ping", source=JobSource.WEB)
    worker = make_worker(stores, executors=default_executors(), tracer=tracer)

    done = worker.process_one()

    assert done is not None and done.status is JobStatus.DONE
    [span] = exporter.get_finished_spans()
    assert span.name == "devops.run"
    assert dict(span.attributes)["devops.command"] == "ping"


def test_main_once_processes_pending(
    monkeypatch: pytest.MonkeyPatch,
    stores: tuple[SqliteJobStore, SqliteAuditStore, SqliteTelemetryStore],
) -> None:
    """CLI 엔트리(`python -m app.worker --once`) e2e — stores_from_env 주입,
    ping job 1건을 외부 호출 없이 DONE 으로 전이(엔트리 배선 + claim→실행→종료 검증)."""
    import sys

    import app.worker as worker_mod

    job_store, audit_store, telemetry_store = stores
    enqueued = job_store.enqueue("ping", source=JobSource.WEB, requested_by="cli")
    monkeypatch.setattr(
        worker_mod,
        "stores_from_env",
        lambda: (job_store, audit_store, telemetry_store),
    )
    monkeypatch.setattr(sys, "argv", ["app.worker", "--once"])

    worker_mod.main()

    done = job_store.get(enqueued.id)
    assert done is not None and done.status is JobStatus.DONE
