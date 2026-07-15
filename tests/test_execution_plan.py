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


# ── 재승인 트리거 ─────────────────────────────────────────────
# 아래 각 케이스는 "승인한 것"과 "지금 실행되려는 것"이 갈라지는 지점이다.
# 갈라지면 실행이 아니라 거부로 끝나야 한다.


def _staged_plan(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, **kwargs: object):
    from app.execution_plan import build_pr_plan as _build

    root = _repository(tmp_path)
    (root / "service.txt").write_text("after\n", encoding="utf-8")
    _git(root, "add", "service.txt")
    diff = _git(root, "diff", "HEAD", "--no-ext-diff", "--binary")
    monkeypatch.setenv("SLACKOPS_WORKSPACE_ROOT", str(root))
    plan = _build("update service", diff, execution_tools=("Read",), **kwargs)  # type: ignore[arg-type]
    return plan, diff


def test_reapproval_on_tool_chain_growth(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    plan, diff = _staged_plan(monkeypatch, tmp_path)
    with pytest.raises(ExecutionPlanError, match="tool chain changed"):
        verify_pr_workspace(
            "update service",
            diff,
            plan.canonical_json(),
            plan.digest(),
            expected_execution_tools=("Read", "Bash(git push:*)"),
        )


def test_reapproval_on_read_to_write_escalation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # 읽기만 승인받은 계획이 실행 직전 쓰기로 올라가면 그 사실을 이름으로 말해야 한다.
    plan, diff = _staged_plan(monkeypatch, tmp_path)
    tampered = plan.canonical_json().replace('"execution_tools":["Read"]', '"execution_tools":["Write"]')
    from app.execution_plan import ExecutionPlan

    swapped = ExecutionPlan.from_json(tampered)
    with pytest.raises(ExecutionPlanError, match="escalated to write capability"):
        verify_pr_workspace(
            "update service",
            diff,
            swapped.canonical_json(),
            swapped.digest(),
            expected_execution_tools=("Write",),
        )


def test_reapproval_on_account_or_region_change(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    plan, diff = _staged_plan(
        monkeypatch, tmp_path, account_id="111122223333", region="us-east-1"
    )
    with pytest.raises(ExecutionPlanError, match="account or region changed"):
        verify_pr_workspace(
            "update service",
            diff,
            plan.canonical_json(),
            plan.digest(),
            expected_execution_tools=("Read",),
            account_id="999988887777",
            region="us-east-1",
        )
    # 같은 대상이면 통과한다 — 트리거가 상시 거부로 퇴화하지 않았는지 확인.
    verify_pr_workspace(
        "update service",
        diff,
        plan.canonical_json(),
        plan.digest(),
        expected_execution_tools=("Read",),
        account_id="111122223333",
        region="us-east-1",
    )
