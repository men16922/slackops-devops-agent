"""Deterministic PR execute — the runtime performs the git plumbing, no model.

These exercise the real git plumbing (branch/add/commit/push) against a temp repo
with a bare `origin`, and inject only the `gh pr create` call so no real GitHub is
touched. This is the path that must reliably open a PR — the LLM execute step it
replaces non-deterministically inspected instead of pushing.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from app.execution_plan import build_pr_plan, current_workspace_diff
from app.pr_execution import PrExecutionError, _branch_name, open_pr
from app.write_credentials import WriteGrant


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, check=True
    ).stdout


def _repo_with_remote(tmp_path: Path) -> Path:
    bare = tmp_path / "origin.git"
    bare.mkdir()
    _git(bare, "init", "--bare")
    work = tmp_path / "work"
    work.mkdir()
    _git(work, "init")
    _git(work, "config", "user.email", "t@example.com")
    _git(work, "config", "user.name", "T")
    _git(work, "checkout", "-b", "main")
    (work / "service.txt").write_text("before\n", encoding="utf-8")
    _git(work, "add", "service.txt")
    _git(work, "commit", "-m", "base")
    _git(work, "remote", "add", "origin", str(bare))
    _git(work, "push", "-u", "origin", "main")
    return work


def _grant() -> WriteGrant:
    return WriteGrant(
        token="t",
        repository="o/n",
        permissions={"contents": "write"},
        expires_at=0.0,
        job_id="j1",
        approval_hash="h1",
        policy_version="secure-runtime-v1",
    )


def _runner_with_gh(pr_url: str = "https://github.com/o/n/pull/1"):
    """Real subprocess for git; a canned success for `gh pr create`."""

    def run(argv, cwd, extra_env):  # type: ignore[no-untyped-def]
        if argv[0] == "gh":
            return subprocess.CompletedProcess(list(argv), 0, stdout=pr_url + "\n", stderr="")
        env = {**os.environ, **(extra_env or {})}
        return subprocess.run(
            list(argv), cwd=str(cwd), env=env, capture_output=True, text=True
        )

    return run


def test_open_pr_branches_commits_pushes_and_returns_url(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = _repo_with_remote(tmp_path)
    (root / "service.txt").write_text("after\n", encoding="utf-8")  # approved change, uncommitted
    monkeypatch.setenv("SLACKOPS_WORKSPACE_ROOT", str(root))
    diff = current_workspace_diff(root)
    plan = build_pr_plan("update service", diff)

    summary = open_pr(
        "update service", plan, _grant(), workspace_root=root, run=_runner_with_gh()
    )

    assert "https://github.com/o/n/pull/1" in summary
    branch = _branch_name(plan)
    assert _git(root, "branch", "--show-current").strip() == branch
    # committed exactly the approved change …
    assert "after" in _git(root, "show", "HEAD:service.txt")
    assert _git(root, "log", "-1", "--pretty=%an").strip() == "slackops-devops-agent"
    # … and pushed the branch to origin.
    remote_refs = _git(root, "ls-remote", "--heads", "origin")
    assert f"refs/heads/{branch}" in remote_refs


def test_open_pr_stages_only_plan_paths(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = _repo_with_remote(tmp_path)
    (root / "service.txt").write_text("after\n", encoding="utf-8")
    monkeypatch.setenv("SLACKOPS_WORKSPACE_ROOT", str(root))
    diff = current_workspace_diff(root)
    plan = build_pr_plan("update service", diff)
    # An unrelated file appears after approval; it must not ride along in the commit.
    (root / "stray.txt").write_text("noise\n", encoding="utf-8")

    open_pr("update service", plan, _grant(), workspace_root=root, run=_runner_with_gh())

    committed = _git(root, "show", "--name-only", "--pretty=format:", "HEAD").split()
    assert committed == ["service.txt"]


def test_open_pr_raises_when_push_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = _repo_with_remote(tmp_path)
    (root / "service.txt").write_text("after\n", encoding="utf-8")
    monkeypatch.setenv("SLACKOPS_WORKSPACE_ROOT", str(root))
    diff = current_workspace_diff(root)
    plan = build_pr_plan("update service", diff)
    _git(root, "remote", "remove", "origin")  # push will fail

    with pytest.raises(PrExecutionError, match="git.*push"):
        open_pr("update service", plan, _grant(), workspace_root=root, run=_runner_with_gh())


def test_open_pr_raises_when_gh_returns_no_url(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = _repo_with_remote(tmp_path)
    (root / "service.txt").write_text("after\n", encoding="utf-8")
    monkeypatch.setenv("SLACKOPS_WORKSPACE_ROOT", str(root))
    diff = current_workspace_diff(root)
    plan = build_pr_plan("update service", diff)

    def run_no_url(argv, cwd, extra_env):  # type: ignore[no-untyped-def]
        if argv[0] == "gh":
            return subprocess.CompletedProcess(list(argv), 0, stdout="created\n", stderr="")
        env = {**os.environ, **(extra_env or {})}
        return subprocess.run(list(argv), cwd=str(cwd), env=env, capture_output=True, text=True)

    with pytest.raises(PrExecutionError, match="no pull-request URL"):
        open_pr("update service", plan, _grant(), workspace_root=root, run=run_no_url)
