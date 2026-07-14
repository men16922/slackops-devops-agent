"""Secure runtime checks for immutable PR execution plans."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from app.execution_plan import (
    ExecutionPlanError,
    build_pr_plan,
    changed_paths,
    verify_pr_workspace,
)


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, check=True
    )
    return result.stdout


def _repository(tmp_path: Path) -> Path:
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Test User")
    (tmp_path / "service.txt").write_text("before\n", encoding="utf-8")
    _git(tmp_path, "add", "service.txt")
    _git(tmp_path, "commit", "-m", "base")
    return tmp_path


def test_changed_paths_rejects_traversal() -> None:
    with pytest.raises(ExecutionPlanError, match="unsafe diff path"):
        changed_paths("--- a/ok.txt\n+++ b/../../outside.txt\n")


def test_plan_hash_binds_args_diff_and_workspace(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = _repository(tmp_path)
    (root / "service.txt").write_text("after\n", encoding="utf-8")
    _git(root, "add", "service.txt")
    diff = _git(root, "diff", "HEAD", "--no-ext-diff", "--binary")
    monkeypatch.setenv("SLACKOPS_WORKSPACE_ROOT", str(root))

    plan = build_pr_plan("update service", diff)
    verified = verify_pr_workspace("update service", diff, plan.canonical_json(), plan.digest())

    assert verified == plan
    with pytest.raises(ExecutionPlanError, match="approved request or diff"):
        verify_pr_workspace("different request", diff, plan.canonical_json(), plan.digest())


def test_workspace_recheck_rejects_symlink_swap(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = _repository(tmp_path)
    target = root / "service.txt"
    target.write_text("after\n", encoding="utf-8")
    _git(root, "add", "service.txt")
    diff = _git(root, "diff", "HEAD", "--no-ext-diff", "--binary")
    monkeypatch.setenv("SLACKOPS_WORKSPACE_ROOT", str(root))
    plan = build_pr_plan("update service", diff)

    target.unlink()
    target.symlink_to("/tmp/outside")

    with pytest.raises(ExecutionPlanError, match="symlink"):
        verify_pr_workspace("update service", diff, plan.canonical_json(), plan.digest())


def test_workspace_recheck_rejects_post_approval_diff_change(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = _repository(tmp_path)
    (root / "service.txt").write_text("after\n", encoding="utf-8")
    _git(root, "add", "service.txt")
    diff = _git(root, "diff", "HEAD", "--no-ext-diff", "--binary")
    monkeypatch.setenv("SLACKOPS_WORKSPACE_ROOT", str(root))
    plan = build_pr_plan("update service", diff)

    (root / "service.txt").write_text("tampered\n", encoding="utf-8")

    with pytest.raises(ExecutionPlanError, match="working tree diff changed"):
        verify_pr_workspace("update service", diff, plan.canonical_json(), plan.digest())


def test_workspace_recheck_rejects_expanded_execution_tool_chain(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = _repository(tmp_path)
    (root / "service.txt").write_text("after\n", encoding="utf-8")
    _git(root, "add", "service.txt")
    diff = _git(root, "diff", "HEAD", "--no-ext-diff", "--binary")
    monkeypatch.setenv("SLACKOPS_WORKSPACE_ROOT", str(root))
    planned_tools = ("Read", "Bash(git push:*)")
    plan = build_pr_plan("update service", diff, execution_tools=planned_tools)

    with pytest.raises(ExecutionPlanError, match="tool chain changed"):
        verify_pr_workspace(
            "update service",
            diff,
            plan.canonical_json(),
            plan.digest(),
            expected_execution_tools=(*planned_tools, "Write"),
        )
