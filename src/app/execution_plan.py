"""Deterministic execution-plan binding for approved write jobs.

The LLM may prepare a change, but it must never define what an approval means.
This module serializes the approved PR diff into a canonical, hash-addressed
plan and checks the workspace again immediately before execution.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath

POLICY_VERSION = "secure-runtime-v1"


class ExecutionPlanError(RuntimeError):
    """The prepared or current execution state violates the approved plan."""


@dataclass(frozen=True)
class ExecutionPlan:
    """Canonical description of the only PR state that may be executed."""

    command: str
    args_sha256: str
    diff_sha256: str
    paths: tuple[str, ...]
    policy_version: str
    workspace_root: str
    execution_tools: tuple[str, ...] = ()
    capabilities: tuple[str, ...] = ()

    def canonical_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))

    def digest(self) -> str:
        return _sha256(self.canonical_json())

    @classmethod
    def from_json(cls, value: str) -> ExecutionPlan:
        try:
            data = json.loads(value)
            if not isinstance(data, dict):
                raise TypeError("execution plan must be an object")
            paths = data.get("paths")
            if not isinstance(paths, list) or not all(isinstance(path, str) for path in paths):
                raise TypeError("execution plan paths must be strings")
            return cls(
                command=str(data["command"]),
                args_sha256=str(data["args_sha256"]),
                diff_sha256=str(data["diff_sha256"]),
                paths=tuple(paths),
                policy_version=str(data["policy_version"]),
                workspace_root=str(data["workspace_root"]),
                execution_tools=tuple(
                    str(tool) for tool in data.get("execution_tools", [])
                ),
                capabilities=tuple(
                    str(capability) for capability in data.get("capabilities", [])
                ),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ExecutionPlanError("invalid execution plan") from exc


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def configured_workspace_root() -> Path:
    """Return the configured canonical workspace root, failing closed if absent."""
    raw = os.environ.get("SLACKOPS_WORKSPACE_ROOT")
    if not raw:
        raise ExecutionPlanError("SLACKOPS_WORKSPACE_ROOT must be configured for PR execution")
    root = Path(raw).resolve(strict=True)
    if not root.is_dir() or not (root / ".git").exists():
        raise ExecutionPlanError("configured workspace root is not a git worktree")
    return root


def changed_paths(diff: str) -> tuple[str, ...]:
    """Extract and normalize every repository-relative path named by a unified diff."""
    paths: set[str] = set()
    for line in diff.splitlines():
        if not (line.startswith("--- ") or line.startswith("+++ ")):
            continue
        raw = line[4:].split("\t", 1)[0]
        if raw == "/dev/null":
            continue
        if raw.startswith(("a/", "b/")):
            raw = raw[2:]
        if not raw:
            raise ExecutionPlanError("diff contains an empty file path")
        path = PurePosixPath(raw)
        if path.is_absolute() or ".." in path.parts or path == PurePosixPath("."):
            raise ExecutionPlanError(f"unsafe diff path: {raw!r}")
        paths.add(path.as_posix())
    if not paths:
        raise ExecutionPlanError("diff does not name any changed paths")
    return tuple(sorted(paths))


def capabilities_for_tools(tools: tuple[str, ...]) -> tuple[str, ...]:
    """Aggregate capabilities from the complete planned tool chain, not one call."""
    capabilities: set[str] = set()
    for tool in tools:
        if tool == "Read" or "get" in tool.lower() or "diff" in tool.lower() or "status" in tool.lower():
            capabilities.add("read")
        if any(token in tool for token in ("Edit", "Write", "commit", "push", "gh pr create")):
            capabilities.add("write-low")
        if any(token in tool.lower() for token in ("iam", "secret", "delete", "apply", "deploy")):
            capabilities.add("privileged")
    return tuple(sorted(capabilities))


def build_pr_plan(
    args: str,
    diff: str,
    *,
    workspace_root: Path | None = None,
    execution_tools: tuple[str, ...] = (),
) -> ExecutionPlan:
    """Build the immutable plan displayed to and approved by the operator."""
    root = workspace_root if workspace_root is not None else configured_workspace_root()
    return ExecutionPlan(
        command="pr",
        args_sha256=_sha256(args.strip()),
        diff_sha256=_sha256(diff),
        paths=changed_paths(diff),
        policy_version=POLICY_VERSION,
        workspace_root=str(root.resolve(strict=True)),
        execution_tools=tuple(sorted(execution_tools)),
        capabilities=capabilities_for_tools(tuple(sorted(execution_tools))),
    )


def _validate_plan_path(root: Path, relative: str) -> None:
    path = PurePosixPath(relative)
    if path.is_absolute() or ".." in path.parts:
        raise ExecutionPlanError(f"unsafe planned path: {relative!r}")
    candidate = root.joinpath(*path.parts)
    # A pre-existing symlink can escape the repository even when its lexical
    # path looks safe. Inspect each existing component before resolving it.
    current = root
    for part in path.parts:
        current = current / part
        if current.is_symlink():
            raise ExecutionPlanError(f"symlink path component is not allowed: {relative!r}")
    try:
        candidate.resolve(strict=False).relative_to(root)
    except ValueError as exc:
        raise ExecutionPlanError(f"planned path escapes workspace: {relative!r}") from exc


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise ExecutionPlanError(f"git verification failed: {result.stderr.strip() or result.stdout.strip()}")
    return result.stdout


def verify_pr_workspace(
    args: str,
    diff: str,
    plan_json: str,
    plan_hash: str,
    *,
    expected_execution_tools: tuple[str, ...] = (),
) -> ExecutionPlan:
    """Verify the exact approved plan and current workspace before write execution."""
    plan = ExecutionPlan.from_json(plan_json)
    if plan.digest() != plan_hash:
        raise ExecutionPlanError("execution plan hash mismatch")
    if plan.command != "pr" or plan.policy_version != POLICY_VERSION:
        raise ExecutionPlanError("unsupported execution plan policy")
    expected_tools = tuple(sorted(expected_execution_tools))
    if plan.execution_tools != expected_tools:
        raise ExecutionPlanError("execution tool chain changed after approval")
    if plan.capabilities != capabilities_for_tools(expected_tools):
        raise ExecutionPlanError("execution capability aggregation changed after approval")
    if plan.args_sha256 != _sha256(args.strip()) or plan.diff_sha256 != _sha256(diff):
        raise ExecutionPlanError("approved request or diff no longer matches the plan")

    root = configured_workspace_root()
    if str(root) != plan.workspace_root:
        raise ExecutionPlanError("workspace root changed after approval")
    for path in plan.paths:
        _validate_plan_path(root, path)

    status = _git(root, "status", "--porcelain")
    if any(line.startswith("?? ") for line in status.splitlines()):
        raise ExecutionPlanError("untracked files are not allowed after approval")
    current_diff = _git(root, "diff", "HEAD", "--no-ext-diff", "--binary")
    if _sha256(current_diff) != plan.diff_sha256:
        raise ExecutionPlanError("working tree diff changed after approval")
    return plan


def verify_remote_pr_diff(summary: str, plan: ExecutionPlan) -> None:
    """Verify that the remote PR diff exactly equals the approved local plan."""
    import re

    match = re.search(r"https://github\.com/[^\s)]+/pull/\d+", summary)
    if match is None:
        raise ExecutionPlanError("PR result did not include a GitHub pull-request URL")
    remote_diff = subprocess.run(
        ["gh", "pr", "diff", match.group(0), "--color=never"],
        capture_output=True,
        text=True,
        check=False,
    )
    if remote_diff.returncode != 0:
        raise ExecutionPlanError(
            f"remote PR verification failed: {remote_diff.stderr.strip() or remote_diff.stdout.strip()}"
        )
    if _sha256(remote_diff.stdout) != plan.diff_sha256:
        raise ExecutionPlanError("remote PR diff differs from the approved execution plan")
