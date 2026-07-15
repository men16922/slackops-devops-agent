"""Audit/Telemetry store 테스트 — Sqlite 와 DynamoDb(moto) 구현을 같은 케이스로 동치 검증.

append/record→조회(list_for_job 시간순, list_feed 일자별 최신순)가 두 구현에서 동일해야 한다.
단일테이블 공존(Job META vs AUDIT#/METRIC# SK)도 검증. 실 AWS 호출 없음(moto).
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

from app.store import (
    AuditEvent,
    DynamoDbAuditStore,
    DynamoDbTelemetryStore,
    MetricRecord,
    SqliteAuditStore,
    SqliteTelemetryStore,
)
from app.store.audit_store import verify_event_chain

os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")

TABLE_NAME = "slackops-agent-test"


def _dynamo_resource() -> object:
    """moto 컨텍스트 안에서 단일테이블이 생성된 dynamodb 리소스."""
    import boto3

    from tests._helpers import create_single_table

    ddb = boto3.resource("dynamodb", region_name="us-east-1")
    create_single_table(ddb, TABLE_NAME)
    return ddb


@pytest.fixture
def audit_store(request: pytest.FixtureRequest) -> Iterator[object]:
    from tests._helpers import counter_clock

    if request.param == "sqlite":
        s = SqliteAuditStore(":memory:", clock=counter_clock())
        yield s
        s.close()
    else:
        from moto import mock_aws

        with mock_aws():
            yield DynamoDbAuditStore(
                TABLE_NAME, dynamodb=_dynamo_resource(), clock=counter_clock()
            )


@pytest.fixture
def metric_store(request: pytest.FixtureRequest) -> Iterator[object]:
    from tests._helpers import counter_clock

    if request.param == "sqlite":
        s = SqliteTelemetryStore(":memory:", clock=counter_clock())
        yield s
        s.close()
    else:
        from moto import mock_aws

        with mock_aws():
            yield DynamoDbTelemetryStore(
                TABLE_NAME, dynamodb=_dynamo_resource(), clock=counter_clock()
            )


def _both_audit(fn: object) -> object:
    return pytest.mark.parametrize("audit_store", ["sqlite", "dynamo"], indirect=True)(fn)


def _both_metric(fn: object) -> object:
    return pytest.mark.parametrize("metric_store", ["sqlite", "dynamo"], indirect=True)(fn)


# ── AuditStore ───────────────────────────────────────────────


@_both_audit
def test_audit_append_roundtrip(audit_store: object) -> None:
    event = audit_store.append("job-1", "claimed", actor="worker", detail="run #1")
    assert isinstance(event, AuditEvent)
    assert (event.job_id, event.action, event.actor, event.detail) == (
        "job-1",
        "claimed",
        "worker",
        "run #1",
    )
    listed = audit_store.list_for_job("job-1")
    assert listed == [event]


@_both_audit
def test_audit_list_for_job_chronological_and_scoped(audit_store: object) -> None:
    audit_store.append("job-1", "enqueued")
    audit_store.append("job-2", "enqueued")  # 다른 job — 섞이면 안 됨
    audit_store.append("job-1", "claimed")
    audit_store.append("job-1", "done")
    actions = [e.action for e in audit_store.list_for_job("job-1")]
    assert actions == ["enqueued", "claimed", "done"]
    assert verify_event_chain(audit_store.list_for_job("job-1"))


@_both_audit
def test_audit_hash_chain_detects_mutation(audit_store: object) -> None:
    audit_store.append("job-1", "enqueued", context={"request_hash": "abc"})
    audit_store.append("job-1", "claimed", context={"policy": "v1"})
    events = audit_store.list_for_job("job-1")
    assert verify_event_chain(events)
    events[1].detail = "tampered"
    assert not verify_event_chain(events)


@_both_audit
def test_audit_list_for_job_unknown_is_empty(audit_store: object) -> None:
    assert audit_store.list_for_job("nope") == []


@_both_audit
def test_audit_feed_newest_first_across_jobs(audit_store: object) -> None:
    audit_store.append("job-1", "enqueued")
    audit_store.append("job-2", "enqueued")
    audit_store.append("job-1", "claimed")
    feed = audit_store.list_feed()
    assert [(e.job_id, e.action) for e in feed] == [
        ("job-1", "claimed"),
        ("job-2", "enqueued"),
        ("job-1", "enqueued"),
    ]


@_both_audit
def test_audit_feed_filters_by_day(audit_store: object) -> None:
    audit_store.append("job-1", "enqueued")  # counter clock → 2026-06-12
    assert audit_store.list_feed(day="20260612") != []
    assert audit_store.list_feed(day="20990101") == []


@_both_audit
def test_audit_same_ts_ordered_by_seq(audit_store: object) -> None:
    """같은 ts 충돌 시 seq 가 정렬을 안정화한다(다발 이벤트 순서 보존)."""
    audit_store._clock = lambda: "2026-06-12T00:00:01.000000Z"  # 고정 clock 주입
    audit_store.append("job-1", "first")
    audit_store.append("job-1", "second")
    audit_store.append("job-1", "third")
    actions = [e.action for e in audit_store.list_for_job("job-1")]
    assert actions == ["first", "second", "third"]


@_both_audit
def test_audit_list_for_job_respects_limit(audit_store: object) -> None:
    for action in ("a", "b", "c"):
        audit_store.append("job-1", action)
    assert [e.action for e in audit_store.list_for_job("job-1", limit=2)] == ["a", "b"]


# ── TelemetryStore ───────────────────────────────────────────


@_both_metric
def test_metric_record_roundtrip_with_numbers(metric_store: object) -> None:
    metric = metric_store.record(
        "job-1",
        command="diagnose",
        duration_ms=1234.5,
        tokens=1500,
        cost_usd=0.0123,
        tool_calls=4,
    )
    assert isinstance(metric, MetricRecord)
    listed = metric_store.list_for_job("job-1")
    assert listed == [metric]
    got = listed[0]
    assert (got.command, got.duration_ms, got.tokens, got.cost_usd, got.tool_calls) == (
        "diagnose",
        1234.5,
        1500,
        0.0123,
        4,
    )
    assert got.success is True
    assert got.error is None


@_both_metric
def test_metric_failure_with_sparse_fields(metric_store: object) -> None:
    metric_store.record("job-1", command="logs", success=False, error="timeout")
    got = metric_store.list_for_job("job-1")[0]
    assert got.success is False
    assert got.error == "timeout"
    assert (got.duration_ms, got.tokens, got.cost_usd, got.tool_calls) == (
        None,
        None,
        None,
        None,
    )


@_both_metric
def test_metric_list_for_job_chronological_and_scoped(metric_store: object) -> None:
    metric_store.record("job-1", command="ping")
    metric_store.record("job-2", command="logs")  # 다른 job — 섞이면 안 됨
    metric_store.record("job-1", command="diagnose")
    commands = [m.command for m in metric_store.list_for_job("job-1")]
    assert commands == ["ping", "diagnose"]


@_both_metric
def test_metric_list_for_job_unknown_is_empty(metric_store: object) -> None:
    assert metric_store.list_for_job("nope") == []


@_both_metric
def test_metric_feed_newest_first_and_day_filter(metric_store: object) -> None:
    metric_store.record("job-1", command="ping")
    metric_store.record("job-2", command="logs")
    feed = metric_store.list_feed()
    assert [m.job_id for m in feed] == ["job-2", "job-1"]
    assert metric_store.list_feed(day="20990101") == []


# ── 단일테이블 공존 (DynamoDB 한정) ──────────────────────────


def test_dynamo_single_table_coexistence() -> None:
    """Job META / AUDIT# / METRIC# 항목이 같은 테이블에서 서로 간섭하지 않는다."""
    from moto import mock_aws

    from app.store import DynamoDbJobStore, JobStatus
    from tests._helpers import counter_clock, counter_id

    with mock_aws():
        ddb = _dynamo_resource()
        jobs = DynamoDbJobStore(
            TABLE_NAME, dynamodb=ddb, clock=counter_clock(), id_factory=counter_id()
        )
        audits = DynamoDbAuditStore(TABLE_NAME, dynamodb=ddb, clock=counter_clock())
        metrics = DynamoDbTelemetryStore(TABLE_NAME, dynamodb=ddb, clock=counter_clock())

        job = jobs.enqueue("logs", "api", requested_by="u1")
        audits.append(job.id, "enqueued", actor="u1")
        metrics.record(job.id, command="logs", cost_usd=0.01)

        # 같은 PK(JOB#{id}) 아래 공존하지만 각 조회는 자기 항목만 본다.
        assert jobs.get(job.id).status is JobStatus.PENDING
        assert [e.action for e in audits.list_for_job(job.id)] == ["enqueued"]
        assert [m.command for m in metrics.list_for_job(job.id)] == ["logs"]

        # GSI2 피드도 항목 타입별로 분리(FEED / AUDIT#day / METRIC#day).
        assert [j.id for j in jobs.list_recent()] == [job.id]
        assert len(audits.list_feed()) == 1
        assert len(metrics.list_feed()) == 1


# ── trajectory 필드 동치 (Sqlite ↔ DynamoDB) ──────────────────


@_both_audit
def test_trajectory_fields_round_trip_on_both_backends(audit_store) -> None:
    # DynamoDB 는 capabilities 를 리스트로, SQLite 는 문자열로 저장한다 —
    # 어느 쪽이든 호출자가 보는 모양은 같아야 한다.
    from app.store import result_digest

    root = audit_store.append("job-1", "claimed", tool_name="pr")
    child = audit_store.append(
        "job-1",
        "write_credentials_issued",
        parent_step_id=root.step_id,
        tool_name="sts:github-app-installation-token",
        capabilities=("read", "write-low"),
        target_resource="repo:o/r",
        result_hash=result_digest("PR opened"),
    )

    events = audit_store.list_for_job("job-1")
    assert [e.step_id for e in events] == [root.step_id, child.step_id]
    restored = events[1]
    assert restored.parent_step_id == root.step_id
    assert restored.capabilities == ("read", "write-low")
    assert restored.target_resource == "repo:o/r"
    assert restored.result_hash == result_digest("PR opened")


@_both_audit
def test_trajectory_chain_verifies_on_both_backends(audit_store) -> None:
    from app.store.audit_store import verify_event_chain

    root = audit_store.append("job-1", "claimed", tool_name="pr")
    audit_store.append("job-1", "done", parent_step_id=root.step_id, tool_name="pr")
    assert verify_event_chain(audit_store.list_for_job("job-1"))
