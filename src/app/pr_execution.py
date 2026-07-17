"""Deterministic PR execute — the runtime performs the git plumbing, not the model.

By the time this runs, the operator-approved plan has been re-verified against the
live worktree and a short-lived write grant has been minted, so the only work left
is mechanical: branch the already-verified working-tree change, commit exactly the
approved paths, push, and open the pull request.

Doing it here with fixed argv (no shell, no model) is why an approved PR reliably
opens: the previous execute step asked a headless model to run commit/push/`gh pr
create`, and the model non-deterministically inspected instead of pushing, or
tried `a && b` compounds the command guard rejects. It also keeps the LLM out of
the write path entirely — the prepare model proposes the change; it never touches
the push. The grant token authenticates git/gh through the child environment and
is revoked by the caller as soon as this returns.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

from app.execution_plan import ExecutionPlan, configured_workspace_root
from app.write_credentials import WriteGrant

# The commit identity. It is intentionally the agent, not the approver: the human
# authorized the change, but the agent performed the write, and the approval↔push
# link lives in the append-only audit trail (WriteGrant.audit_context), not in an
# impersonated Git author.
COMMIT_NAME = "slackops-devops-agent"
COMMIT_EMAIL = "slackops-devops-agent[bot]@users.noreply.github.com"

# Title/body derive from the operator-approved request. Titles stay short so the
# PR list is readable; the full request rides in the body.
_MAX_TITLE_CHARS = 72

# A completed subprocess result — the injected runner returns one of these so tests
# never touch a real git remote or GitHub.
CommandRunner = Callable[[Sequence[str], Path, Mapping[str, str] | None], "subprocess.CompletedProcess[str]"]


class PrExecutionError(RuntimeError):
    """A deterministic git/gh step failed while opening the approved PR."""


def _default_runner(
    argv: Sequence[str], cwd: Path, extra_env: Mapping[str, str] | None
) -> "subprocess.CompletedProcess[str]":
    import os

    env = {**os.environ, **extra_env} if extra_env else None
    return subprocess.run(
        list(argv), cwd=str(cwd), env=env, capture_output=True, text=True, check=False
    )


def _branch_name(plan: ExecutionPlan) -> str:
    """A branch name unique to this approval (its plan digest), collision-free per job."""
    return f"slackops/pr-{plan.digest()[:12]}"


def _title_and_body(description: str) -> tuple[str, str]:
    first_line = description.strip().splitlines()[0].strip() if description.strip() else "Automated change"
    title = first_line[:_MAX_TITLE_CHARS].rstrip() or "Automated change"
    body = (
        f"{description.strip()}\n\n"
        "---\n"
        ":lock: Opened by the SlackOps DevOps agent after human approval of the diff. "
        "Branch protection requires a human to review and merge."
    )
    return title, body


def _extract_pr_url(stdout: str) -> str | None:
    import re

    match = re.search(r"https://github\.com/[^\s]+/pull/\d+", stdout)
    return match.group(0) if match else None


def open_pr(
    description: str,
    plan: ExecutionPlan,
    grant: WriteGrant,
    *,
    workspace_root: Path | None = None,
    run: CommandRunner = _default_runner,
) -> str:
    """Deterministically open the approved PR and return a Slack-ready summary.

    The caller has already re-verified ``plan`` against the live worktree and minted
    ``grant``; this stages exactly ``plan.paths`` (the worktree is known to hold only
    the approved change), commits, pushes a per-approval branch, and opens the PR.

    Raises:
        PrExecutionError: any git/gh step failed, or ``gh pr create`` returned no
            pull-request URL — the job then fails rather than reporting a PR that
            does not exist.
    """
    root = workspace_root if workspace_root is not None else configured_workspace_root()
    env = grant.child_env()
    branch = _branch_name(plan)
    title, body = _title_and_body(description)

    def _step(argv: Sequence[str], *, with_grant: bool = False) -> "subprocess.CompletedProcess[str]":
        result = run(argv, root, env if with_grant else None)
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip()
            raise PrExecutionError(f"`{' '.join(argv)}` failed: {detail}")
        return result

    # Carry the already-verified working-tree change onto a fresh per-approval branch,
    # then stage only the approved paths — verify_pr_workspace already proved the tree
    # holds exactly this change and no untracked files, so nothing else can ride along.
    _step(["git", "checkout", "-b", branch])
    _step(["git", "add", "--", *plan.paths])
    _step(
        [
            "git",
            "-c",
            f"user.name={COMMIT_NAME}",
            "-c",
            f"user.email={COMMIT_EMAIL}",
            "commit",
            "-m",
            title,
        ]
    )
    _step(["git", "push", "-u", "origin", "HEAD"], with_grant=True)
    created = _step(
        ["gh", "pr", "create", "--title", title, "--body", body], with_grant=True
    )

    url = _extract_pr_url(created.stdout) or _extract_pr_url(created.stderr)
    if url is None:
        raise PrExecutionError(
            "gh pr create returned no pull-request URL: "
            f"{(created.stdout or created.stderr).strip()}"
        )

    _verify_remote_paths(url, plan, root, env, run)
    return f":white_check_mark: Pull request opened: {url}"


def _verify_remote_paths(
    url: str,
    plan: ExecutionPlan,
    root: Path,
    env: Mapping[str, str],
    run: CommandRunner,
) -> None:
    """Confirm the opened PR changes exactly the approved set of paths.

    This runs here — inside the deterministic execute, with the grant in ``env``
    — rather than as a later worker step, because the worker process has no
    GitHub credential and ``gh`` would fail to authenticate. Content is already
    guaranteed by construction (the committed tree was byte-verified against the
    approved diff); this catches a wrong-branch or path-set surprise on the
    remote. It deliberately does not byte-compare ``gh pr diff`` against the local
    ``git diff HEAD --binary`` — the two are different textual formats, so an
    exact-bytes check fails even on a correct PR.
    """
    from app.execution_plan import ExecutionPlanError, changed_paths

    result = run(["gh", "pr", "diff", url, "--color=never"], root, env)
    if result.returncode != 0:
        raise PrExecutionError(
            f"remote PR verification failed: {(result.stderr or result.stdout).strip()}"
        )
    try:
        remote_paths = changed_paths(result.stdout)
    except ExecutionPlanError as exc:
        raise PrExecutionError(f"could not read the remote PR diff: {exc}") from exc
    if remote_paths != tuple(plan.paths):
        raise PrExecutionError(
            "remote PR changes a different set of paths than approved: "
            f"{list(remote_paths)} vs {list(plan.paths)}"
        )
