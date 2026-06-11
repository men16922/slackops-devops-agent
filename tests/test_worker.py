"""worker 폴링 루프 테스트 — SqliteJobStore + mock 으로 claim→실행→전이 e2e.

실 AWS/Claude/subprocess 호출 없음: runner/fetcher/executors/monotonic/sleep 전부 주입.
"""

from __future__ import annotations

import pytest

from app.commands import logs
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
        AUDIT_DONE,
    ]


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
    jobs, _, _ = stores
    jobs.enqueue("rm-rf", source=JobSource.WEB)
    worker = make_worker(stores, executors={})

    failed = worker.process_one()

    assert failed is not None
    assert failed.status is JobStatus.FAILED
    assert failed.error is not None and "default deny" in failed.error
