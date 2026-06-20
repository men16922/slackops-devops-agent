"""detection_config store 테스트 — Sqlite/DynamoDb(moto) 동치(set/get/list round-trip)."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

from app.store import (
    DetectionConfig,
    DynamoDbDetectionConfigStore,
    SqliteDetectionConfigStore,
)

os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")

TABLE_NAME = "slackops-agent-test"


def _dynamo_resource() -> object:
    import boto3

    from tests._helpers import create_single_table

    ddb = boto3.resource("dynamodb", region_name="us-east-1")
    create_single_table(ddb, TABLE_NAME)
    return ddb


@pytest.fixture(params=["sqlite", "dynamo"])
def store(request: pytest.FixtureRequest) -> Iterator[object]:
    from tests._helpers import counter_clock

    if request.param == "sqlite":
        s = SqliteDetectionConfigStore(":memory:", clock=counter_clock())
        yield s
        s.close()
    else:
        from moto import mock_aws

        with mock_aws():
            yield DynamoDbDetectionConfigStore(
                TABLE_NAME, dynamodb=_dynamo_resource(), clock=counter_clock()
            )


def test_set_get_roundtrip(store: object) -> None:
    cfg = store.set_config("iam", enabled=True, mode="scheduled")  # type: ignore[attr-defined]
    assert isinstance(cfg, DetectionConfig)
    got = store.get_config("iam")  # type: ignore[attr-defined]
    assert got is not None
    assert got.enabled is True
    assert got.mode == "scheduled"
    assert got.updated_at  # clock 기록됨


def test_get_missing_returns_none(store: object) -> None:
    assert store.get_config("nope") is None  # type: ignore[attr-defined]


def test_set_overwrites(store: object) -> None:
    store.set_config("config", enabled=True)  # type: ignore[attr-defined]
    store.set_config("config", enabled=False, mode="on-demand")  # type: ignore[attr-defined]
    got = store.get_config("config")  # type: ignore[attr-defined]
    assert got is not None
    assert got.enabled is False


def test_list_configs_sorted(store: object) -> None:
    store.set_config("ssm", enabled=True)  # type: ignore[attr-defined]
    store.set_config("iam", enabled=False)  # type: ignore[attr-defined]
    cats = [c.category for c in store.list_configs()]  # type: ignore[attr-defined]
    assert cats == sorted(cats)
    assert set(cats) == {"ssm", "iam"}
