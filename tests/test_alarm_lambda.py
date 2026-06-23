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
    # ① 알림은 SSM/네트워크 의존 → 핸들러 테스트에선 no-op 로 차단(별도 단위테스트로 검증).
    monkeypatch.setattr(alarm_lambda, "notify_detected", lambda *a, **k: True)
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


# ── ① "문제 인지" 알림 ─────────────────────────────────────────────


def test_format_detected_includes_cmd_and_rationale() -> None:
    text = alarm_lambda.format_detected("diagnose", "checkout-service", "Detected 5xx spike")
    assert "diagnose" in text
    assert "checkout-service" in text
    assert "Detected 5xx spike" in text


def test_notify_detected_posts_then_swallows_failure() -> None:
    sent: list[str] = []
    assert alarm_lambda.notify_detected("diagnose", "svc", "why", post=sent.append) is True
    assert sent and "diagnose" in sent[0]

    def boom(_text: str) -> None:
        raise RuntimeError("slack down")

    # 게시 실패는 swallow — producer/제안에 영향 없음.
    assert alarm_lambda.notify_detected("diagnose", "svc", "why", post=boom) is False


def test_handler_notifies_new_proposal_only(
    monkeypatch: pytest.MonkeyPatch, store: SqliteJobStore
) -> None:
    monkeypatch.setattr(alarm_lambda, "store_from_env", lambda: store)
    calls: list[tuple[str, str, str]] = []
    monkeypatch.setattr(
        alarm_lambda,
        "notify_detected",
        lambda c, a, r: (calls.append((c, a, r)), True)[1],
    )
    alarm_lambda.handler(_event("ALARM", reason=_DEMO_REASON))  # 새 제안 → ① 알림
    alarm_lambda.handler(_event("ALARM", reason=_DEMO_REASON))  # 중복 → 알림 안 함
    assert len(calls) == 1
    assert calls[0][0] == "diagnose"
    assert calls[0][1] == "checkout-service"
