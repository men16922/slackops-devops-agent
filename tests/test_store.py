"""JobStore 테스트 — SqliteJobStore 와 DynamoDbJobStore(moto)를 같은 케이스로 동치 검증.

두 구현이 동일하게 동작해야 한다(claim 원자성·상태머신·출력 게이트). 실 AWS 호출 없음(moto).
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator

import pytest

from app.store import Job, JobSource, JobStatus, SqliteJobStore
from app.store.dynamodb_store import DynamoDbJobStore

os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")

TABLE_NAME = "slackops-agent-test"


def _counter_clock() -> Callable[[], str]:
    state = {"i": 0}

    def clock() -> str:
        state["i"] += 1
        return f"2026-06-12T00:00:{state['i']:02d}.000000Z"

    return clock


def _counter_id() -> Callable[[], str]:
    state = {"i": 0}

    def idf() -> str:
        state["i"] += 1
        return f"job-{state['i']}"

    return idf


def _create_table(dynamodb: object) -> None:
    """제출 데이터모델대로 단일테이블 + GSI1/GSI2 생성(deploy provisioning 과 동일 스키마)."""
    dynamodb.create_table(  # type: ignore[attr-defined]
        TableName=TABLE_NAME,
        BillingMode="PAY_PER_REQUEST",
        KeySchema=[
            {"AttributeName": "PK", "KeyType": "HASH"},
            {"AttributeName": "SK", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "PK", "AttributeType": "S"},
            {"AttributeName": "SK", "AttributeType": "S"},
            {"AttributeName": "GSI1PK", "AttributeType": "S"},
            {"AttributeName": "GSI1SK", "AttributeType": "S"},
            {"AttributeName": "GSI2PK", "AttributeType": "S"},
            {"AttributeName": "GSI2SK", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "GSI1",
                "KeySchema": [
                    {"AttributeName": "GSI1PK", "KeyType": "HASH"},
                    {"AttributeName": "GSI1SK", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
            {
                "IndexName": "GSI2",
                "KeySchema": [
                    {"AttributeName": "GSI2PK", "KeyType": "HASH"},
                    {"AttributeName": "GSI2SK", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
        ],
    )


@pytest.fixture
def store(request: pytest.FixtureRequest) -> Iterator[object]:
    """두 구현을 같은 테스트로 돌리기 위한 parametrized 스토어 픽스처."""
    if request.param == "sqlite":
        s = SqliteJobStore(":memory:", clock=_counter_clock(), id_factory=_counter_id())
        yield s
        s.close()
    else:
        from moto import mock_aws

        with mock_aws():
            import boto3

            ddb = boto3.resource("dynamodb", region_name="us-east-1")
            _create_table(ddb)
            yield DynamoDbJobStore(
                TABLE_NAME, dynamodb=ddb, clock=_counter_clock(), id_factory=_counter_id()
            )


def _both(fn: object) -> object:
    return pytest.mark.parametrize("store", ["sqlite", "dynamo"], indirect=True)(fn)


# ── producer / readers ───────────────────────────────────────


@_both
def test_enqueue_creates_pending_job(store: object) -> None:
    job = store.enqueue("logs", "api", source=JobSource.WEB, requested_by="u1")
    assert isinstance(job, Job)
    assert job.status is JobStatus.PENDING
    assert (job.command, job.args, job.requested_by) == ("logs", "api", "u1")
    assert store.get(job.id).status is JobStatus.PENDING


@_both
def test_get_missing_returns_none(store: object) -> None:
    assert store.get("nope") is None


@_both
def test_list_recent_newest_first(store: object) -> None:
    store.enqueue("ping")
    second = store.enqueue("logs", "api")
    recent = store.list_recent(limit=10)
    assert recent[0].id == second.id


# ── claim 원자성 / FIFO / 우선순위 ───────────────────────────


@_both
def test_claim_is_fifo_and_marks_running(store: object) -> None:
    first = store.enqueue("logs", "a")
    store.enqueue("logs", "b")
    claimed = store.claim()
    assert claimed.id == first.id
    assert claimed.status is JobStatus.RUNNING


@_both
def test_claim_empty_returns_none(store: object) -> None:
    assert store.claim() is None


@_both
def test_claim_does_not_double_claim(store: object) -> None:
    store.enqueue("ping")
    assert store.claim() is not None
    assert store.claim() is None  # 이미 RUNNING — 재claim 불가


@_both
def test_claim_prioritizes_approved_over_pending(store: object) -> None:
    """승인된 쓰기 이어가기가 신규 PENDING 보다 우선."""
    approved = store.enqueue("pr", "fix")
    store.claim()  # approved → RUNNING
    store.await_approval(approved.id, diff="--- diff ---")
    store.approve(approved.id, approver="boss")
    store.enqueue("logs", "later")  # PENDING

    claimed = store.claim()
    assert claimed.id == approved.id
    assert claimed.status is JobStatus.RUNNING


# ── 출력 게이트 상태머신 ─────────────────────────────────────


@_both
def test_output_gate_full_flow(store: object) -> None:
    job = store.enqueue("pr", "add feature", source=JobSource.SLACK)
    store.claim()  # RUNNING
    gated = store.await_approval(job.id, diff="patch")
    assert gated.status is JobStatus.AWAITING_APPROVAL
    assert gated.diff == "patch"

    approved = store.approve(job.id, approver="alice")
    assert approved.status is JobStatus.APPROVED
    assert approved.approved_by == "alice"

    store.claim()  # APPROVED → RUNNING
    done = store.complete(job.id, status=JobStatus.DONE, result="merged", cost_usd=0.02, tokens=1500)
    assert done.status is JobStatus.DONE
    assert (done.result, done.cost_usd, done.tokens) == ("merged", 0.02, 1500)


@_both
def test_approve_wrong_state_is_noop(store: object) -> None:
    job = store.enqueue("pr", "x")  # PENDING, 승인 대기 아님
    assert store.approve(job.id, approver="a") is None
    assert store.get(job.id).status is JobStatus.PENDING


@_both
def test_reject_makes_job_unclaimable(store: object) -> None:
    job = store.enqueue("pr", "x")
    store.claim()
    store.await_approval(job.id, diff="d")
    rejected = store.reject(job.id, approver="a")
    assert rejected.status is JobStatus.REJECTED
    assert store.claim() is None  # REJECTED 는 claim 대상 아님


@_both
def test_complete_failed_records_error(store: object) -> None:
    job = store.enqueue("logs", "svc")
    store.claim()
    failed = store.complete(job.id, status=JobStatus.FAILED, error="boom")
    assert failed.status is JobStatus.FAILED
    assert failed.error == "boom"
