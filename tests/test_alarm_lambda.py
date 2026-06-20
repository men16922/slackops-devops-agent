"""alarm_lambda 순수 로직 테스트 — EventBridge CloudWatch Alarm 이벤트 → 제안 적재.

store_from_env 를 in-memory SqliteJobStore 로 monkeypatch — AWS 불필요.
"""

from __future__ import annotations

from typing import Any

import pytest

from app import alarm_lambda
from app.store import JobSource, JobStatus, SqliteJobStore
from tests._helpers import counter_clock, counter_id


def _event(state: str = "ALARM", *, name: str = "slackops-demo-checkout-5xx", reason: str = "") -> dict[str, Any]:
    return {
        "source": "aws.cloudwatch",
        "detail-type": "CloudWatch Alarm State Change",
        "detail": {
            "alarmName": name,
            "state": {"value": state, "reason": reason},
            "previousState": {"value": "OK"},
        },
    }


# 강제 데모 alarm 의 실제 StateReason(cloud-alarm.sh 와 동일 마커).
_DEMO_REASON = (
    "demo: service=checkout-service ALB 5xx error rate 23% over 5m; "
    "upstream 504 gateway timeout; p99 8.1s"
)


@pytest.fixture
def store() -> SqliteJobStore:
    return SqliteJobStore(":memory:", clock=counter_clock(), id_factory=counter_id())


@pytest.fixture
def patched(monkeypatch: pytest.MonkeyPatch, store: SqliteJobStore) -> SqliteJobStore:
    monkeypatch.setattr(alarm_lambda, "store_from_env", lambda: store)
    return store


def test_is_alarm_event() -> None:
    assert alarm_lambda.is_alarm_event(_event("ALARM")) is True
    assert alarm_lambda.is_alarm_event(_event("OK")) is False
    assert alarm_lambda.is_alarm_event(_event("INSUFFICIENT_DATA")) is False
    assert alarm_lambda.is_alarm_event({}) is False


def test_build_signal_includes_name_and_reason() -> None:
    sig = alarm_lambda.build_signal(_event(reason=_DEMO_REASON))
    assert "slackops-demo-checkout-5xx" in sig
    assert "service=checkout-service" in sig


def test_alarm_event_proposes_diagnose(patched: SqliteJobStore) -> None:
    res = alarm_lambda.handler(_event("ALARM", reason=_DEMO_REASON))
    assert res["proposed"] is True
    job = patched.get(str(res["result"]["job_id"]))
    assert job is not None
    assert job.source is JobSource.AGENT
    assert job.status is JobStatus.PENDING
    assert job.command == "diagnose"
    assert job.args == "checkout-service"
    assert job.rationale is not None
    assert job.rationale.startswith("Detected error-rate spike")  # i18n 안전망: 영어 rationale


def test_non_alarm_event_ignored(patched: SqliteJobStore) -> None:
    res = alarm_lambda.handler(_event("OK", reason=_DEMO_REASON))
    assert res["proposed"] is False
    assert res["ignored"] == "state != ALARM"
    assert patched.list_recent() == []


def test_alarm_without_marker_no_proposal(patched: SqliteJobStore) -> None:
    # 일반 임계치 메시지 — service/5xx/error 마커 없음 → 보수적으로 미제안.
    res = alarm_lambda.handler(_event("ALARM", name="cpu-high", reason="Threshold Crossed: cpu 91%"))
    assert res["proposed"] is False
    assert patched.list_recent() == []


def test_duplicate_alarm_deduped(patched: SqliteJobStore) -> None:
    first = alarm_lambda.handler(_event("ALARM", reason=_DEMO_REASON))
    second = alarm_lambda.handler(_event("ALARM", reason=_DEMO_REASON))
    assert first["result"].get("deduped") is not True
    assert second["result"]["deduped"] is True  # 같은 open agent 제안 → 무해 no-op
    assert len(patched.list_recent()) == 1
