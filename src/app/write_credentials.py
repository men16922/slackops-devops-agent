"""Approval-bound, short-lived write credentials for the execute step.

The diagnosis path holds no write capability at all: `logs`/`diagnose`/`detect`
run against fixed read adapters, and the PR *prepare* step runs with no write
credential in its environment, so it cannot push even if the model is convinced
to try.  A write credential exists only after :func:`issue_pr_write_grant` has
re-verified that the operator-approved plan hash still binds the exact work about
to run, and it exists only inside the environment of that one child process.

The grant is scoped at issue time — one repository, two permissions, a short
expiry — and revoked as soon as the step returns.  Because a GitHub installation
token carries no session tags, the jobId/approvalHash/policyVersion binding is
recorded in the append-only audit trail instead (see
:meth:`WriteGrant.audit_context`), which is what links a real push back to the
approval that authorized it.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from collections.abc import Generator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Protocol

from app.execution_plan import POLICY_VERSION, WRITE_LOW, ExecutionPlan, risk_score

# GitHub caps installation tokens at one hour; the execute step is a single
# push + `gh pr create`, so it does not need anywhere near that.
DEFAULT_GRANT_TTL_S = 600

# The only permissions the execute step needs: push the prepared branch and open
# the pull request. Notably absent: `administration`, `workflows`, `secrets`.
PR_GRANT_PERMISSIONS: Mapping[str, str] = {
    "contents": "write",
    "pull_requests": "write",
}

_GITHUB_API = "https://api.github.com"


class WriteCredentialError(Exception):
    """A write credential was requested without a verified approval binding."""


@dataclass(frozen=True)
class WriteGrant:
    """One short-lived write credential bound to one approved job.

    Attributes:
        token: the secret. Never logged, never audited, never returned to Slack.
        repository: `owner/name` the token is scoped to.
        permissions: the exact permission set requested at issue time.
        expires_at: unix seconds after which the token is dead regardless of revoke.
        job_id / approval_hash / policy_version: the approval this grant answers to.
    """

    token: str = field(repr=False)
    repository: str
    permissions: Mapping[str, str]
    expires_at: float
    job_id: str
    approval_hash: str
    policy_version: str

    def __repr__(self) -> str:  # pragma: no cover - trivial redaction
        return (
            f"WriteGrant(repository={self.repository!r}, job_id={self.job_id!r}, "
            f"approval_hash={self.approval_hash!r}, token=<redacted>)"
        )

    def audit_context(self) -> dict[str, str]:
        """Audit fields that bind this credential to its approval — no secret."""
        return {
            "job_id": self.job_id,
            "approval_hash": self.approval_hash,
            "policy_version": self.policy_version,
            "repository": self.repository,
            "permissions": ",".join(f"{k}:{v}" for k, v in sorted(self.permissions.items())),
            "expires_in_s": str(max(0, int(self.expires_at - time.time()))),
        }

    def child_env(self) -> dict[str, str]:
        """Environment for the one child process allowed to use this grant.

        `git push` authenticates through gh's credential helper rather than a
        file, so the token never lands on disk and dies with the process env.
        """
        return {
            "GH_TOKEN": self.token,
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": "credential.https://github.com.helper",
            "GIT_CONFIG_VALUE_0": "!gh auth git-credential",
        }


class GrantIssuer(Protocol):
    """Mints and revokes a repository-scoped short-lived token."""

    def issue(self, repository: str, permissions: Mapping[str, str]) -> tuple[str, float]:
        """Return (token, expires_at_unix_seconds)."""
        ...

    def revoke(self, token: str) -> None:
        """Best-effort immediate invalidation."""
        ...


def _require_approval_binding(job: object, plan: ExecutionPlan) -> tuple[str, str]:
    """Fail closed unless this job carries a verified, current approval binding."""
    job_id = getattr(job, "id", None)
    approved_by = getattr(job, "approved_by", None)
    approval_hash = getattr(job, "approval_hash", None)
    plan_hash = getattr(job, "execution_plan_hash", None)
    if not isinstance(job_id, str) or not job_id:
        raise WriteCredentialError("write grant requires an identified job")
    if approved_by is None:
        raise WriteCredentialError("write grant requires an approved job")
    if not isinstance(approval_hash, str) or not approval_hash:
        raise WriteCredentialError("write grant requires an approval hash")
    if approval_hash != plan_hash:
        raise WriteCredentialError("approval hash does not match the execution plan hash")
    # The plan object is the one the worker just re-verified against the live
    # workspace; re-deriving the digest here means a swapped plan cannot smuggle
    # a stale approval through.
    if plan.digest() != approval_hash:
        raise WriteCredentialError("verified plan does not match the approval hash")
    if plan.policy_version != POLICY_VERSION:
        raise WriteCredentialError("execution plan policy version is not current")
    # Re-score the approved capability set rather than trusting the stored number,
    # and hold it to the ceiling that was in force when the operator approved.
    score = risk_score(plan.capabilities)
    if score != plan.risk_score:
        raise WriteCredentialError(
            f"plan risk score does not match its capabilities: {plan.risk_score} vs {score}"
        )
    if score > plan.risk_ceiling:
        raise WriteCredentialError(
            f"plan risk {score} exceeds the approved ceiling {plan.risk_ceiling}"
        )
    if WRITE_LOW not in plan.capabilities:
        raise WriteCredentialError("execution plan does not carry a write capability")
    return job_id, approval_hash


def issue_pr_write_grant(
    job: object,
    plan: ExecutionPlan,
    *,
    repository: str,
    issuer: GrantIssuer,
) -> WriteGrant:
    """Issue the only write credential the approved PR execute step may use.

    Args:
        job: the approved job (needs id/approved_by/approval_hash/execution_plan_hash).
        plan: the execution plan the worker has already re-verified.
        repository: `owner/name` the grant is fixed to.
        issuer: token source (injected — tests never reach GitHub).

    Raises:
        WriteCredentialError: any missing or mismatched approval binding.
    """
    job_id, approval_hash = _require_approval_binding(job, plan)
    if "/" not in repository.strip("/"):
        raise WriteCredentialError(f"write grant needs an owner/name repository: {repository!r}")
    token, expires_at = issuer.issue(repository, PR_GRANT_PERMISSIONS)
    if not token:
        raise WriteCredentialError("credential issuer returned an empty token")
    return WriteGrant(
        token=token,
        repository=repository,
        permissions=dict(PR_GRANT_PERMISSIONS),
        expires_at=expires_at,
        job_id=job_id,
        approval_hash=approval_hash,
        policy_version=plan.policy_version,
    )


@contextmanager
def pr_write_grant(
    job: object,
    plan: ExecutionPlan,
    *,
    repository: str,
    issuer: GrantIssuer,
) -> Generator[WriteGrant]:
    """Hold an approved PR write grant for exactly the duration of one step.

    The credential is revoked on the way out whether the step succeeded, failed,
    or raised — expiry is the backstop, not the plan.
    """
    grant = issue_pr_write_grant(job, plan, repository=repository, issuer=issuer)
    try:
        yield grant
    finally:
        issuer.revoke(grant.token)


class GitHubAppGrantIssuer:
    """Mints repository-scoped installation tokens from a GitHub App private key.

    A GitHub App installation token is the only GitHub credential that is both
    short-lived and narrowable to a single repository and permission set, which
    is why the agent holds an App key (root-owned, via SSM) instead of a personal
    access token that would be standing write access.
    """

    def __init__(
        self,
        app_id: str,
        installation_id: str,
        private_key_pem: str,
        *,
        api_base: str = _GITHUB_API,
        ttl_s: int = DEFAULT_GRANT_TTL_S,
    ) -> None:
        self._app_id = app_id
        self._installation_id = installation_id
        self._private_key_pem = private_key_pem
        self._api_base = api_base.rstrip("/")
        self._ttl_s = ttl_s

    def _app_jwt(self) -> str:
        import jwt  # lazy: only the EC2 write path needs the signing dependency

        now = int(time.time())
        return jwt.encode(
            {"iat": now - 60, "exp": now + 540, "iss": self._app_id},
            self._private_key_pem,
            algorithm="RS256",
        )

    def _post(self, path: str, bearer: str, payload: Mapping[str, object] | None) -> dict[str, object]:
        body = json.dumps(payload).encode() if payload is not None else None
        request = urllib.request.Request(
            f"{self._api_base}{path}",
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {bearer}",
                "Accept": "application/vnd.github+json",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 - fixed https host
            parsed = json.loads(response.read().decode())
        if not isinstance(parsed, dict):
            raise WriteCredentialError("unexpected GitHub token response")
        return parsed

    def issue(self, repository: str, permissions: Mapping[str, str]) -> tuple[str, float]:
        """Mint a token scoped to exactly one repository and permission set."""
        name = repository.split("/", 1)[1]
        try:
            parsed = self._post(
                f"/app/installations/{self._installation_id}/access_tokens",
                self._app_jwt(),
                {"repositories": [name], "permissions": dict(permissions)},
            )
        except urllib.error.URLError as exc:
            raise WriteCredentialError(f"could not mint a write credential: {exc}") from None
        token = parsed.get("token")
        if not isinstance(token, str) or not token:
            raise WriteCredentialError("GitHub returned no installation token")
        return token, time.time() + self._ttl_s

    def revoke(self, token: str) -> None:
        """Invalidate the token immediately; expiry is the backstop, not the plan."""
        request = urllib.request.Request(
            f"{self._api_base}/installation/token",
            method="DELETE",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
            },
        )
        try:
            urllib.request.urlopen(request, timeout=30).close()  # noqa: S310 - fixed https host
        except urllib.error.URLError:
            # The grant still expires on its own; a failed revoke must not turn a
            # completed, approved PR into a failed job.
            return
