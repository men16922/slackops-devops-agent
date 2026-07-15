"""write_credentials — write 자격은 승인 결속이 재검증된 뒤에만, 그 단계 동안만 존재한다."""

from __future__ import annotations

import time
from collections.abc import Mapping

import pytest

from app.execution_plan import POLICY_VERSION, RISK_CEILING, ExecutionPlan, risk_score
from app.write_credentials import (
    PR_GRANT_PERMISSIONS,
    WriteCredentialError,
    WriteGrant,
    issue_pr_write_grant,
    pr_write_grant,
)


class FakeIssuer:
    """실 GitHub 대신 발급/회수를 기록한다."""

    def __init__(self, token: str = "ghs_secret_token") -> None:
        self.token = token
        self.issued: list[tuple[str, dict[str, str]]] = []
        self.revoked: list[str] = []

    def issue(self, repository: str, permissions: Mapping[str, str]) -> tuple[str, float]:
        self.issued.append((repository, dict(permissions)))
        return self.token, time.time() + 600

    def revoke(self, token: str) -> None:
        self.revoked.append(token)


class FakeJob:
    def __init__(
        self,
        *,
        job_id: str = "job-1",
        approved_by: str | None = "U_APPROVER",
        approval_hash: str | None = None,
        plan_hash: str | None = None,
    ) -> None:
        self.id = job_id
        self.approved_by = approved_by
        self.approval_hash = approval_hash
        self.execution_plan_hash = plan_hash


def make_plan(
    *,
    capabilities: tuple[str, ...] = ("read", "write-low"),
    policy_version: str = POLICY_VERSION,
    score: int | None = None,
    ceiling: int = RISK_CEILING,
) -> ExecutionPlan:
    return ExecutionPlan(
        command="pr",
        args_sha256="a" * 64,
        diff_sha256="b" * 64,
        paths=("src/app/worker.py",),
        policy_version=policy_version,
        workspace_root="/opt/slackops-devops-agent",
        execution_tools=("Bash(git push:*)",),
        capabilities=capabilities,
        risk_score=risk_score(capabilities) if score is None else score,
        risk_ceiling=ceiling,
    )


def approved(plan: ExecutionPlan, **kwargs: object) -> FakeJob:
    digest = plan.digest()
    defaults: dict[str, object] = {"approval_hash": digest, "plan_hash": digest}
    defaults.update(kwargs)
    return FakeJob(**defaults)  # type: ignore[arg-type]


class TestApprovalBinding:
    def test_issues_for_a_verified_approved_job(self) -> None:
        plan = make_plan()
        issuer = FakeIssuer()
        grant = issue_pr_write_grant(
            approved(plan), plan, repository="men16922/slackops-devops-agent", issuer=issuer
        )
        assert grant.token == "ghs_secret_token"
        assert grant.approval_hash == plan.digest()
        assert issuer.issued == [
            ("men16922/slackops-devops-agent", dict(PR_GRANT_PERMISSIONS))
        ]

    def test_unapproved_job_gets_no_credential(self) -> None:
        plan = make_plan()
        job = approved(plan, approved_by=None)
        with pytest.raises(WriteCredentialError, match="approved job"):
            issue_pr_write_grant(job, plan, repository="o/r", issuer=FakeIssuer())

    def test_approval_hash_must_match_the_plan_hash(self) -> None:
        plan = make_plan()
        job = approved(plan, approval_hash="c" * 64)
        with pytest.raises(WriteCredentialError, match="does not match the execution plan hash"):
            issue_pr_write_grant(job, plan, repository="o/r", issuer=FakeIssuer())

    def test_swapped_plan_cannot_reuse_a_stale_approval(self) -> None:
        # 승인 당시 plan 과 지금 실행하려는 plan 이 다르면 자격이 나오지 않는다(TOCTOU).
        approved_plan = make_plan()
        job = approved(approved_plan)
        other_plan = make_plan(capabilities=("read", "write-low", "privileged"))
        with pytest.raises(WriteCredentialError):
            issue_pr_write_grant(job, other_plan, repository="o/r", issuer=FakeIssuer())

    def test_privileged_capability_exceeds_the_ceiling(self) -> None:
        # privileged(50) 는 그 자체로 ceiling(10) 을 넘는다 — 특례가 아니라 산술이다.
        plan = make_plan(capabilities=("read", "write-low", "privileged"))
        with pytest.raises(WriteCredentialError, match="exceeds the approved ceiling"):
            issue_pr_write_grant(approved(plan), plan, repository="o/r", issuer=FakeIssuer())

    def test_write_high_exceeds_the_ceiling(self) -> None:
        plan = make_plan(capabilities=("read", "write-high"))
        with pytest.raises(WriteCredentialError, match="exceeds the approved ceiling"):
            issue_pr_write_grant(approved(plan), plan, repository="o/r", issuer=FakeIssuer())

    def test_tampered_risk_score_is_refused(self) -> None:
        # 저장된 점수를 낮춰 ceiling 을 통과시키려는 시도는 재계산으로 드러난다.
        plan = make_plan(capabilities=("read", "write-low", "privileged"), score=6)
        with pytest.raises(WriteCredentialError, match="does not match its capabilities"):
            issue_pr_write_grant(approved(plan), plan, repository="o/r", issuer=FakeIssuer())

    def test_raised_ceiling_cannot_retroactively_bless_an_approval(self) -> None:
        # 승인 당시 ceiling 이 기준이다 — 나중에 정책이 느슨해져도 이 승인엔 적용되지 않는다.
        plan = make_plan(capabilities=("read", "write-high"), ceiling=3)
        with pytest.raises(WriteCredentialError, match="exceeds the approved ceiling 3"):
            issue_pr_write_grant(approved(plan), plan, repository="o/r", issuer=FakeIssuer())

    def test_read_only_plan_gets_no_write_credential(self) -> None:
        plan = make_plan(capabilities=("read",))
        with pytest.raises(WriteCredentialError, match="write capability"):
            issue_pr_write_grant(approved(plan), plan, repository="o/r", issuer=FakeIssuer())

    def test_stale_policy_version_is_rejected(self) -> None:
        plan = make_plan(policy_version="secure-runtime-v0")
        with pytest.raises(WriteCredentialError, match="policy version"):
            issue_pr_write_grant(approved(plan), plan, repository="o/r", issuer=FakeIssuer())

    def test_repository_must_be_owner_name(self) -> None:
        plan = make_plan()
        with pytest.raises(WriteCredentialError, match="owner/name"):
            issue_pr_write_grant(approved(plan), plan, repository="justname", issuer=FakeIssuer())

    def test_empty_token_fails_closed(self) -> None:
        plan = make_plan()
        with pytest.raises(WriteCredentialError, match="empty token"):
            issue_pr_write_grant(
                approved(plan), plan, repository="o/r", issuer=FakeIssuer(token="")
            )


class TestGrantLifetime:
    def test_context_revokes_on_success(self) -> None:
        plan = make_plan()
        issuer = FakeIssuer()
        with pr_write_grant(approved(plan), plan, repository="o/r", issuer=issuer) as grant:
            assert grant.token
            assert issuer.revoked == []
        assert issuer.revoked == ["ghs_secret_token"]

    def test_context_revokes_on_failure(self) -> None:
        plan = make_plan()
        issuer = FakeIssuer()
        with pytest.raises(RuntimeError):
            with pr_write_grant(approved(plan), plan, repository="o/r", issuer=issuer):
                raise RuntimeError("push blew up")
        assert issuer.revoked == ["ghs_secret_token"]


class TestSecretHandling:
    def test_repr_redacts_the_token(self) -> None:
        plan = make_plan()
        grant = issue_pr_write_grant(
            approved(plan), plan, repository="o/r", issuer=FakeIssuer()
        )
        assert "ghs_secret_token" not in repr(grant)
        assert "<redacted>" in repr(grant)

    def test_audit_context_binds_approval_without_the_secret(self) -> None:
        plan = make_plan()
        grant = issue_pr_write_grant(
            approved(plan), plan, repository="o/r", issuer=FakeIssuer()
        )
        context = grant.audit_context()
        assert context["approval_hash"] == plan.digest()
        assert context["policy_version"] == POLICY_VERSION
        assert context["permissions"] == "contents:write,pull_requests:write"
        assert "ghs_secret_token" not in "".join(context.values())

    def test_child_env_carries_the_token_and_no_disk_credential(self) -> None:
        grant = WriteGrant(
            token="ghs_x",
            repository="o/r",
            permissions=dict(PR_GRANT_PERMISSIONS),
            expires_at=time.time() + 60,
            job_id="job-1",
            approval_hash="h",
            policy_version=POLICY_VERSION,
        )
        env = grant.child_env()
        assert env["GH_TOKEN"] == "ghs_x"
        # git 은 gh 의 credential helper 로 인증한다 — 토큰이 디스크에 남지 않는다.
        assert env["GIT_CONFIG_VALUE_0"] == "!gh auth git-credential"
