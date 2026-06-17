"""JobStore 의 DynamoDB 단일테이블 구현 (운영 — 이중 컨트롤플레인 공유 큐).

테이블 `slackops-agent`(on-demand). 키 설계:
  Job   PK=JOB#{id}  SK=META    GSI1=STATUS#{status}/{created_at}  GSI2=FEED/{created_at}
claim 은 GSI1(STATUS#…) 질의 → ConditionExpression(status=expected) UpdateItem 으로 원자적 전이
(optimistic lock) — 동시 worker 의 중복 실행을 막는다. SQLite 의 BEGIN IMMEDIATE claim 과 1:1 대응.

boto3 는 lazy import — 미설치 환경에서도 모듈 import-safe. dynamodb 리소스를 주입하면
moto(테스트)/DynamoDB Local 로 실 AWS 없이 동작한다.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

from app.store._util import encode_for_dynamodb as _encode, utcnow_iso as _utcnow_iso
from app.store.base import (
    CLAIMABLE_STATUSES,
    Job,
    JobSource,
    JobStatus,
)

META_SK = "META"
FEED_PK = "FEED"
_CLAIM_SCAN_LIMIT = 10  # 경합 시 다음 후보까지 시도할 최대 수


class DynamoDbJobStore:
    """DynamoDB 단일테이블 JobStore 구현."""

    def __init__(
        self,
        table_name: str = "slackops-agent",
        *,
        dynamodb: Any | None = None,
        clock: Callable[[], str] | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._clock = clock or _utcnow_iso
        self._id_factory = id_factory or (lambda: str(uuid.uuid4()))
        if dynamodb is None:
            import boto3  # lazy: 미설치/자격증명 없는 환경 import-safe

            dynamodb = boto3.resource("dynamodb")
        self._table = dynamodb.Table(table_name)

    # ── producer ──────────────────────────────────────────────
    def enqueue(
        self,
        command: str,
        args: str = "",
        *,
        source: JobSource = JobSource.WEB,
        requested_by: str = "",
        channel: str | None = None,
        rationale: str | None = None,
    ) -> Job:
        now = self._clock()
        job = Job(
            id=self._id_factory(),
            command=command,
            args=args,
            source=source,
            status=JobStatus.PENDING,
            requested_by=requested_by,
            channel=channel,
            created_at=now,
            updated_at=now,
            rationale=rationale,
        )
        self._table.put_item(Item=_to_item(job))
        return job

    # ── readers ───────────────────────────────────────────────
    def get(self, job_id: str) -> Job | None:
        resp = self._table.get_item(Key={"PK": f"JOB#{job_id}", "SK": META_SK})
        item = resp.get("Item")
        return _from_item(item) if item else None

    def list_recent(self, limit: int = 50) -> list[Job]:
        from boto3.dynamodb.conditions import Key  # lazy

        resp = self._table.query(
            IndexName="GSI2",
            KeyConditionExpression=Key("GSI2PK").eq(FEED_PK),
            ScanIndexForward=False,  # 최신순
            Limit=limit,
        )
        return [_from_item(item) for item in resp.get("Items", [])]

    # ── consumer (worker) ─────────────────────────────────────
    def claim(self) -> Job | None:
        """APPROVED 우선, 그다음 PENDING 중 가장 오래된 1건을 원자적으로 RUNNING 으로."""
        from boto3.dynamodb.conditions import Key  # lazy

        for status in CLAIMABLE_STATUSES:
            resp = self._table.query(
                IndexName="GSI1",
                KeyConditionExpression=Key("GSI1PK").eq(f"STATUS#{status.value}"),
                ScanIndexForward=True,  # 오래된 것부터
                Limit=_CLAIM_SCAN_LIMIT,
            )
            for item in resp.get("Items", []):
                claimed = self._conditional_set(
                    item["id"], expected=status, new=JobStatus.RUNNING, extra={}
                )
                if claimed is not None:
                    return claimed
        return None

    # ── 출력 게이트 / 종료 ─────────────────────────────────────
    def await_approval(self, job_id: str, diff: str) -> Job | None:
        return self._conditional_set(
            job_id,
            expected=JobStatus.RUNNING,
            new=JobStatus.AWAITING_APPROVAL,
            extra={"diff": diff},
        )

    def approve(self, job_id: str, approver: str) -> Job | None:
        return self._conditional_set(
            job_id,
            expected=JobStatus.AWAITING_APPROVAL,
            new=JobStatus.APPROVED,
            extra={"approved_by": approver, "approved_at": self._clock()},
        )

    def reject(self, job_id: str, approver: str) -> Job | None:
        return self._conditional_set(
            job_id,
            expected=JobStatus.AWAITING_APPROVAL,
            new=JobStatus.REJECTED,
            extra={"approved_by": approver, "approved_at": self._clock()},
        )

    def complete(
        self,
        job_id: str,
        *,
        status: JobStatus,
        result: str | None = None,
        cost_usd: float | None = None,
        tokens: int | None = None,
        error: str | None = None,
    ) -> Job | None:
        return self._conditional_set(
            job_id,
            expected=JobStatus.RUNNING,
            new=status,
            extra={
                "result": result,
                "cost_usd": cost_usd,
                "tokens": tokens,
                "error": error,
            },
        )

    # ── 내부 ──────────────────────────────────────────────────
    def _conditional_set(
        self,
        job_id: str,
        *,
        expected: JobStatus,
        new: JobStatus,
        extra: dict[str, object],
    ) -> Job | None:
        """status==expected 일 때만 new 로 전이(+GSI1PK 동기화, extra 갱신). 불일치면 None."""
        from botocore.exceptions import ClientError  # lazy

        # status·error·result 등은 DynamoDB 예약어 — extra 필드는 전부 #fN 별칭으로 SET.
        names = {"#s": "status"}
        set_parts = ["#s = :new", "GSI1PK = :gpk", "updated_at = :now"]
        values: dict[str, object] = {
            ":new": new.value,
            ":gpk": f"STATUS#{new.value}",
            ":now": self._clock(),
            ":expected": expected.value,
        }
        for i, (key, value) in enumerate(extra.items()):
            if value is None:
                continue
            name_ref, value_ref = f"#f{i}", f":f{i}"
            names[name_ref] = key
            set_parts.append(f"{name_ref} = {value_ref}")
            values[value_ref] = _encode(value)
        try:
            resp = self._table.update_item(
                Key={"PK": f"JOB#{job_id}", "SK": META_SK},
                UpdateExpression="SET " + ", ".join(set_parts),
                ConditionExpression="#s = :expected",
                ExpressionAttributeNames=names,
                ExpressionAttributeValues=values,
                ReturnValues="ALL_NEW",
            )
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
                return None
            raise
        return _from_item(resp["Attributes"])


def _to_item(job: Job) -> dict[str, Any]:
    item: dict[str, Any] = {
        "PK": f"JOB#{job.id}",
        "SK": META_SK,
        "GSI1PK": f"STATUS#{job.status.value}",
        "GSI1SK": job.created_at,
        "GSI2PK": FEED_PK,
        "GSI2SK": job.created_at,
        "id": job.id,
        "command": job.command,
        "args": job.args,
        "source": job.source.value,
        "status": job.status.value,
        "requested_by": job.requested_by,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    }
    optional = {
        "channel": job.channel,
        "diff": job.diff,
        "result": job.result,
        "cost_usd": job.cost_usd,
        "tokens": job.tokens,
        "error": job.error,
        "approved_by": job.approved_by,
        "approved_at": job.approved_at,
        "trace_id": job.trace_id,
        "rationale": job.rationale,
    }
    for key, value in optional.items():
        if value is not None:
            item[key] = _encode(value)
    return item


def _from_item(item: dict[str, Any]) -> Job:
    cost = item.get("cost_usd")
    tokens = item.get("tokens")
    return Job(
        id=item["id"],
        command=item["command"],
        args=item.get("args", ""),
        source=JobSource(item["source"]),
        status=JobStatus(item["status"]),
        requested_by=item.get("requested_by", ""),
        channel=item.get("channel"),
        created_at=item["created_at"],
        updated_at=item["updated_at"],
        diff=item.get("diff"),
        result=item.get("result"),
        cost_usd=float(cost) if cost is not None else None,
        tokens=int(tokens) if tokens is not None else None,
        error=item.get("error"),
        approved_by=item.get("approved_by"),
        approved_at=item.get("approved_at"),
        trace_id=item.get("trace_id"),
        rationale=item.get("rationale"),
    )
