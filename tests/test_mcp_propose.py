"""mcp_server 순수 로직 테스트 — propose_job_impl / list_pending_impl (SDK 불필요).

FastMCP 래퍼는 build_server 스모크(mcp 미설치면 skip)로만 확인한다.
"""

from __future__ import annotations

import pytest

from app.mcp_server import list_pending_impl, propose_job_impl
from app.store import JobSource, JobStatus, SqliteJobStore
from tests._helpers import counter_clock, counter_id


@pytest.fixture
def store() -> SqliteJobStore:
    return SqliteJobStore(":memory:", clock=counter_clock(), id_factory=counter_id())


def test_propose_known_command_enqueues_agent_job(store: SqliteJobStore) -> None:
    res = propose_job_impl(store, "diagnose", "api", "5xx 급증 감지")
    assert res["ok"] is True
    job = store.get(str(res["job_id"]))
    assert job is not None
    assert job.source is JobSource.AGENT
    assert job.status is JobStatus.PENDING
    assert job.command == "diagnose"
    assert job.args == "api"
    assert job.requested_by == "agent"
    assert job.rationale == "5xx 급증 감지"


def test_propose_unknown_command_rejected(store: SqliteJobStore) -> None:
    """미지 명령은 default deny — 큐에 적재되지 않는다(주입 방어)."""
    res = propose_job_impl(store, "rm-rf", "/", "malicious")
    assert res["ok"] is False
    assert "default deny" in str(res["error"])
    assert store.list_recent() == []


def test_propose_forbidden_keyword_rejected(store: SqliteJobStore) -> None:
    """금지 불변(apply/deploy 등)도 거부."""
    assert propose_job_impl(store, "deploy", "prod", "x")["ok"] is False
    assert propose_job_impl(store, "apply", "", "x")["ok"] is False


def test_propose_empty_rationale_stores_none(store: SqliteJobStore) -> None:
    res = propose_job_impl(store, "ping", "", "")
    job = store.get(str(res["job_id"]))
    assert job is not None
    assert job.rationale is None


def test_list_pending_filters_to_pending_and_awaiting(store: SqliteJobStore) -> None:
    # 먼저 logs 를 넣고 done 으로 보낸다(claim 은 FIFO 라 가장 오래된 pending 을 집음).
    done = store.enqueue("logs", "x")
    store.claim()  # logs → running
    store.complete(done.id, status=JobStatus.DONE)
    # 그 뒤 에이전트가 diagnose 제안(pending).
    propose_job_impl(store, "diagnose", "api", "r1")
    pending = list_pending_impl(store)
    cmds = {p["command"] for p in pending}
    assert "diagnose" in cmds
    assert "logs" not in cmds  # done 은 제외


def test_propose_dedupes_identical_open_agent_job(store: SqliteJobStore) -> None:
    """동일 (command, args) AGENT 제안이 이미 열려있으면 두 번째는 dedupe(무해 no-op)."""
    first = propose_job_impl(store, "diagnose", "api", "r1")
    assert first["ok"] is True
    assert isinstance(first["job_id"], str)
    second = propose_job_impl(store, "diagnose", "api", "r2")
    assert second["ok"] is True
    assert second.get("deduped") is True
    assert second["job_id"] is None
    assert len(store.list_recent()) == 1


def test_propose_not_deduped_when_args_differ(store: SqliteJobStore) -> None:
    propose_job_impl(store, "diagnose", "api", "r")
    res = propose_job_impl(store, "diagnose", "web", "r")
    assert res.get("deduped") is not True
    assert isinstance(res["job_id"], str)
    assert len(store.list_recent()) == 2


def test_propose_not_deduped_after_terminal(store: SqliteJobStore) -> None:
    """dedupe 는 '열려있는' 동안만 — done 이 되면 같은 제안을 다시 올릴 수 있다."""
    first = propose_job_impl(store, "diagnose", "api", "r")
    store.claim()  # pending → running
    store.complete(str(first["job_id"]), status=JobStatus.DONE)
    res = propose_job_impl(store, "diagnose", "api", "r")
    assert res.get("deduped") is not True
    assert isinstance(res["job_id"], str)
    assert len(store.list_recent()) == 2


def test_propose_dedupe_scoped_to_agent(store: SqliteJobStore) -> None:
    """사람/web 가 동일 명령을 넣어도 agent 제안은 별개로 적재(의도적 재제출 보존)."""
    store.enqueue("diagnose", "api", source=JobSource.WEB)
    res = propose_job_impl(store, "diagnose", "api", "r")
    assert res.get("deduped") is not True
    assert isinstance(res["job_id"], str)
    assert len(store.list_recent()) == 2


def test_build_server_smoke() -> None:
    """FastMCP 래퍼가 구성되는지 — mcp SDK 미설치 환경이면 skip."""
    pytest.importorskip("mcp")
    from app.mcp_server import build_server

    server = build_server(SqliteJobStore(":memory:"))
    assert server is not None
