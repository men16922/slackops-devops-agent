"""worker ↔ write credential 배선 — 자격은 승인된 execute 단계에만 존재한다."""

from __future__ import annotations

import base64
import time
from contextlib import nullcontext
from typing import Any

import pytest

from app.execution_plan import POLICY_VERSION, ExecutionPlan
from app.store import (
    JobSource,
    SqliteAuditStore,
    SqliteJobStore,
    SqliteTelemetryStore,
)
from app.worker import (
    AUDIT_WRITE_CREDENTIALS_ISSUED,
    PR_REPOSITORY_ENV,
    Worker,
    default_executors,
    grant_issuer_from_env,
)
from app.write_credentials import PR_GRANT_PERMISSIONS, WriteGrant
from tests._helpers import counter_clock, counter_id

_PLAN = ExecutionPlan(
    command="pr",
    args_sha256="a" * 64,
    diff_sha256="b" * 64,
    paths=("x.py",),
    policy_version=POLICY_VERSION,
    workspace_root="/test/workspace",
    execution_tools=("Bash(git push:*)",),
    capabilities=("read", "write-low"),
)


def _grant(job_id: str = "job-1") -> WriteGrant:
    return WriteGrant(
        token="ghs_secret",
        repository="men16922/slackops-devops-agent",
        permissions=dict(PR_GRANT_PERMISSIONS),
        expires_at=time.time() + 600,
        job_id=job_id,
        approval_hash=_PLAN.digest(),
        policy_version=POLICY_VERSION,
    )


class RecordingProvider:
    """grant 컨텍스트의 열림/닫힘과 대상 job 을 기록한다."""

    def __init__(self) -> None:
        self.opened: list[str] = []
        self.closed: list[str] = []

    def __call__(self, job: Any, plan: ExecutionPlan) -> Any:
        from contextlib import contextmanager

        @contextmanager
        def cm():  # type: ignore[no-untyped-def]
            self.opened.append(job.id)
            try:
                yield _grant(job.id)
            finally:
                self.closed.append(job.id)

        return cm()


class FakePrModule:
    """pr.handle_pr 대역 — 어떤 write_grant 로 불렸는지 기록."""

    def __init__(self) -> None:
        self.grants: list[WriteGrant | None] = []

    def handle_pr(self, _args: str, **kwargs: Any) -> Any:
        self.grants.append(kwargs.get("write_grant"))

        class _Result:
            summary = "PR opened: https://github.com/o/r/pull/1"
            diff = None if kwargs.get("approved_diff") else "diff --git a/x.py b/x.py"

        return _Result()


@pytest.fixture()
def fake_pr(monkeypatch: pytest.MonkeyPatch) -> FakePrModule:
    from app.commands import pr as pr_mod

    fake = FakePrModule()
    monkeypatch.setattr(pr_mod, "handle_pr", fake.handle_pr)
    return fake


class _Job:
    def __init__(self, approved: bool) -> None:
        self.id = "job-1"
        self.args = "fix the thing"
        self.command = "pr"
        self.approved_by = "U_APPROVER" if approved else None
        self.diff = "diff --git a/x.py b/x.py" if approved else None
        self.approval_hash = _PLAN.digest() if approved else None
        self.execution_plan_hash = _PLAN.digest() if approved else None


class TestGrantOnlyOnApprovedExecute:
    def test_prepare_never_opens_a_grant(self, fake_pr: FakePrModule) -> None:
        provider = RecordingProvider()
        executors = default_executors(grant_provider=provider)
        executors["pr"](_Job(approved=False))  # type: ignore[arg-type]
        # prepare 프로세스에는 push 자격 자체가 없다 — 도구 제거에만 기대지 않는다.
        assert provider.opened == []
        assert fake_pr.grants == [None]

    def test_approved_execute_issues_then_revokes(
        self, fake_pr: FakePrModule, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import app.worker as worker_mod

        monkeypatch.setattr(worker_mod, "_verify_approved_pr", lambda _job: _PLAN)
        provider = RecordingProvider()
        executors = default_executors(grant_provider=provider)
        executors["pr"](_Job(approved=True))  # type: ignore[arg-type]

        assert provider.opened == ["job-1"]
        # 자격은 그 단계가 끝나면 회수된다 — 만료는 보조 수단이다.
        assert provider.closed == ["job-1"]
        assert fake_pr.grants[0] is not None
        assert fake_pr.grants[0].approval_hash == _PLAN.digest()

    def test_grant_is_refused_when_plan_verification_fails(
        self, fake_pr: FakePrModule, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import app.worker as worker_mod

        def _reject(_job: Any) -> ExecutionPlan:
            raise ExecutionPlanErrorStub("working tree diff changed after approval")

        from app.execution_plan import ExecutionPlanError as ExecutionPlanErrorStub

        monkeypatch.setattr(worker_mod, "_verify_approved_pr", _reject)
        provider = RecordingProvider()
        executors = default_executors(grant_provider=provider)
        with pytest.raises(ExecutionPlanErrorStub):
            executors["pr"](_Job(approved=True))  # type: ignore[arg-type]
        # 검증이 깨지면 자격은 발급되지 않고 handle_pr 도 호출되지 않는다.
        assert provider.opened == []
        assert fake_pr.grants == []


class TestAuditBinding:
    def test_issued_grant_is_audited_without_the_secret(self) -> None:
        jobs = SqliteJobStore(clock=counter_clock(), id_factory=counter_id())
        audit = SqliteAuditStore(clock=counter_clock())
        metrics = SqliteTelemetryStore(clock=counter_clock())
        worker = Worker(
            jobs,
            audit,
            metrics,
            grant_provider=lambda job, plan: nullcontext(_grant(job.id)),
        )
        job = jobs.enqueue("pr", args="fix", source=JobSource.SLACK)

        with worker._audited_grant(job, _PLAN) as grant:  # noqa: SLF001 - wiring under test
            assert grant is not None

        events = audit.list_for_job(job.id)
        issued = [e for e in events if e.action == AUDIT_WRITE_CREDENTIALS_ISSUED]
        assert len(issued) == 1
        assert issued[0].context["approval_hash"] == _PLAN.digest()
        assert issued[0].context["policy_version"] == POLICY_VERSION
        assert "ghs_secret" not in str(issued[0].context) + issued[0].detail

    def test_unconfigured_runtime_audits_nothing(self) -> None:
        jobs = SqliteJobStore(clock=counter_clock(), id_factory=counter_id())
        audit = SqliteAuditStore(clock=counter_clock())
        metrics = SqliteTelemetryStore(clock=counter_clock())
        worker = Worker(
            jobs, audit, metrics, grant_provider=lambda _job, _plan: nullcontext(None)
        )
        job = jobs.enqueue("pr", args="fix", source=JobSource.SLACK)
        with worker._audited_grant(job, _PLAN) as grant:  # noqa: SLF001
            assert grant is None
        assert [e for e in audit.list_for_job(job.id) if e.action == AUDIT_WRITE_CREDENTIALS_ISSUED] == []


class TestEnvConfiguration:
    def test_unconfigured_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for name in (
            PR_REPOSITORY_ENV,
            "SLACKOPS_GITHUB_APP_ID",
            "SLACKOPS_GITHUB_INSTALLATION_ID",
            "SLACKOPS_GITHUB_APP_PRIVATE_KEY_B64",
        ):
            monkeypatch.delenv(name, raising=False)
        assert grant_issuer_from_env() is None

    def test_partial_configuration_fails_loudly(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # "설정했다고 믿었는데 조용히 자격이 없는" 상태와 의도적 미구성을 구분한다.
        monkeypatch.setenv(PR_REPOSITORY_ENV, "men16922/slackops-devops-agent")
        for name in (
            "SLACKOPS_GITHUB_APP_ID",
            "SLACKOPS_GITHUB_INSTALLATION_ID",
            "SLACKOPS_GITHUB_APP_PRIVATE_KEY_B64",
        ):
            monkeypatch.delenv(name, raising=False)
        with pytest.raises(ValueError, match="incomplete"):
            grant_issuer_from_env()

    def test_full_configuration_builds_issuer(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(PR_REPOSITORY_ENV, "men16922/slackops-devops-agent")
        monkeypatch.setenv("SLACKOPS_GITHUB_APP_ID", "12345")
        monkeypatch.setenv("SLACKOPS_GITHUB_INSTALLATION_ID", "67890")
        monkeypatch.setenv(
            "SLACKOPS_GITHUB_APP_PRIVATE_KEY_B64",
            base64.b64encode(b"-----BEGIN RSA PRIVATE KEY-----").decode(),
        )
        configured = grant_issuer_from_env()
        assert configured is not None
        repository, _issuer = configured
        assert repository == "men16922/slackops-devops-agent"

    def test_non_base64_private_key_fails_loudly(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # PEM 을 base64 없이 그대로 넣는 흔한 실수를 부팅이 아니라 여기서 드러낸다.
        monkeypatch.setenv(PR_REPOSITORY_ENV, "men16922/slackops-devops-agent")
        monkeypatch.setenv("SLACKOPS_GITHUB_APP_ID", "12345")
        monkeypatch.setenv("SLACKOPS_GITHUB_INSTALLATION_ID", "67890")
        monkeypatch.setenv(
            "SLACKOPS_GITHUB_APP_PRIVATE_KEY_B64", "-----BEGIN RSA PRIVATE KEY-----"
        )
        with pytest.raises(ValueError, match="base64"):
            grant_issuer_from_env()
