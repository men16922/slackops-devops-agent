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

# Capability taxonomy. A tool's class is declared (see _TOOL_CAPABILITIES), never
# inferred from its spelling: substring matching silently dropped `git add`,
# `git checkout`, `python -m pytest` and `terraform plan` into *no* capability at
# all, which made the aggregate risk of a tool chain read lower than it was.
READ = "read"
SENSITIVE_READ = "sensitive-read"
WRITE_LOW = "write-low"
WRITE_HIGH = "write-high"
PRIVILEGED = "privileged"

# Risk is scored per distinct capability and summed across the whole chain, so a
# plan combining several individually-modest tools is not scored as though it
# were only the single riskiest one.
_CAPABILITY_RISK: dict[str, int] = {
    READ: 1,
    SENSITIVE_READ: 4,
    WRITE_LOW: 5,
    WRITE_HIGH: 20,
    PRIVILEGED: 50,
}

# The ceiling a single approved plan may reach. write-high (20) and privileged
# (50) exceed it on their own, so "L2 stays disabled" and "privileged is blocked"
# become one arithmetic rule rather than a list of special cases.
RISK_CEILING = 10


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
    # Aggregate risk and the ceiling in force, both frozen at approval time: a
    # later policy that raises the ceiling cannot retroactively bless this plan.
    risk_score: int = 0
    risk_ceiling: int = RISK_CEILING
    # The account/region the operator approved. Re-checked before execution so an
    # environment change invalidates the approval instead of silently retargeting.
    account_id: str = ""
    region: str = ""

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
                risk_score=int(data.get("risk_score", 0)),
                risk_ceiling=int(data.get("risk_ceiling", RISK_CEILING)),
                account_id=str(data.get("account_id", "")),
                region=str(data.get("region", "")),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ExecutionPlanError("invalid execution plan") from exc


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _write_capabilities(capabilities: tuple[str, ...]) -> set[str]:
    """The subset that can change something outside this process."""
    return {c for c in capabilities if c in (WRITE_LOW, WRITE_HIGH, PRIVILEGED)}


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


# Declared capability of every tool the allowlist can hand to a model.
# allowlist.py cross-checks this at import — a tool added on one side only is an
# import error, not a plan whose risk is quietly understated.
_TOOL_CAPABILITIES: dict[str, str] = {
    "Read": READ,
    "Edit": WRITE_LOW,
    "Write": WRITE_LOW,
    "Bash(git status:*)": READ,
    "Bash(git diff:*)": READ,
    "Bash(git checkout:*)": WRITE_LOW,
    "Bash(git add:*)": WRITE_LOW,
    "Bash(git commit:*)": WRITE_LOW,
    "Bash(git push:*)": WRITE_LOW,
    "Bash(gh pr create:*)": WRITE_LOW,
    # pytest executes repository code and may leave artifacts in the workspace;
    # classify by what it can do, not by the fact that it is "just tests".
    "Bash(python -m pytest:*)": WRITE_LOW,
    "Bash(terraform plan:*)": READ,
    "Bash(terraform show:*)": READ,
}


def declared_tools() -> frozenset[str]:
    """Tools with a declared capability (mirrors the allowlist)."""
    return frozenset(_TOOL_CAPABILITIES)


def capabilities_for_tools(tools: tuple[str, ...]) -> tuple[str, ...]:
    """Aggregate capabilities across the complete planned tool chain, not one call.

    Raises:
        ExecutionPlanError: a tool has no declared capability — an unclassified
            tool must not be scored as harmless.
    """
    capabilities: set[str] = set()
    for tool in tools:
        try:
            capabilities.add(_TOOL_CAPABILITIES[tool])
        except KeyError:
            raise ExecutionPlanError(f"tool has no declared capability: {tool!r}") from None
    return tuple(sorted(capabilities))


def risk_score(capabilities: tuple[str, ...]) -> int:
    """Score the aggregate capability of a plan.

    Raises:
        ExecutionPlanError: an unknown capability — fail closed rather than score 0.
    """
    total = 0
    for capability in capabilities:
        try:
            total += _CAPABILITY_RISK[capability]
        except KeyError:
            raise ExecutionPlanError(f"unknown capability: {capability!r}") from None
    return total


def build_pr_plan(
    args: str,
    diff: str,
    *,
    workspace_root: Path | None = None,
    execution_tools: tuple[str, ...] = (),
    account_id: str = "",
    region: str = "",
) -> ExecutionPlan:
    """Build the immutable plan displayed to and approved by the operator.

    Raises:
        ExecutionPlanError: the aggregate risk of the tool chain exceeds the
            ceiling — such a plan is never offered for approval, so an operator
            cannot be asked to bless something the policy would refuse anyway.
    """
    root = workspace_root if workspace_root is not None else configured_workspace_root()
    capabilities = capabilities_for_tools(tuple(sorted(execution_tools)))
    score = risk_score(capabilities)
    if score > RISK_CEILING:
        raise ExecutionPlanError(
            f"planned tool chain risk {score} exceeds the ceiling {RISK_CEILING}: "
            f"capabilities={list(capabilities)}"
        )
    return ExecutionPlan(
        command="pr",
        args_sha256=_sha256(args.strip()),
        diff_sha256=_sha256(diff),
        paths=changed_paths(diff),
        policy_version=POLICY_VERSION,
        workspace_root=str(root.resolve(strict=True)),
        execution_tools=tuple(sorted(execution_tools)),
        capabilities=capabilities,
        risk_score=score,
        risk_ceiling=RISK_CEILING,
        account_id=account_id,
        region=region,
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


def current_workspace_diff(root: Path | None = None) -> str:
    """The runtime's authoritative working-tree diff versus HEAD.

    This is the single source of truth for the approved diff. prepare displays
    and hashes exactly this, and verify_pr_workspace re-computes exactly this
    before execution, so the two can never disagree over the model's textual
    approximation of its own change (the printed diff between markers carried a
    fake ``index``/``@@`` line that never byte-matched the real tree, which made
    execute always fail closed with ``plan_binding_rejected``).
    """
    r = root if root is not None else configured_workspace_root()
    return _git(r, "diff", "HEAD", "--no-ext-diff", "--binary")


def verify_pr_workspace(
    args: str,
    diff: str,
    plan_json: str,
    plan_hash: str,
    *,
    expected_execution_tools: tuple[str, ...] = (),
    account_id: str = "",
    region: str = "",
) -> ExecutionPlan:
    """Verify the exact approved plan and current workspace before write execution.

    Every check here is a re-approval trigger: if it fires, the approval no longer
    describes what is about to run, and the job fails rather than executing a
    plan the operator did not see.
    """
    plan = ExecutionPlan.from_json(plan_json)
    if plan.digest() != plan_hash:
        raise ExecutionPlanError("execution plan hash mismatch")
    if plan.command != "pr" or plan.policy_version != POLICY_VERSION:
        raise ExecutionPlanError("unsupported execution plan policy")
    expected_tools = tuple(sorted(expected_execution_tools))
    if plan.execution_tools != expected_tools:
        raise ExecutionPlanError("execution tool chain changed after approval")
    current_capabilities = capabilities_for_tools(expected_tools)
    if plan.capabilities != current_capabilities:
        approved_writes = _write_capabilities(plan.capabilities)
        current_writes = _write_capabilities(current_capabilities)
        if current_writes - approved_writes:
            raise ExecutionPlanError(
                "execution escalated to write capability after approval: "
                f"{sorted(current_writes - approved_writes)}"
            )
        raise ExecutionPlanError("execution capability aggregation changed after approval")
    # Re-score rather than trust the stored number, and compare against the
    # ceiling that was in force at approval — not today's.
    current_score = risk_score(current_capabilities)
    if current_score != plan.risk_score:
        raise ExecutionPlanError(
            f"execution risk score changed after approval: {plan.risk_score} → {current_score}"
        )
    if current_score > plan.risk_ceiling:
        raise ExecutionPlanError(
            f"execution risk {current_score} exceeds the approved ceiling {plan.risk_ceiling}"
        )
    if plan.account_id != account_id or plan.region != region:
        raise ExecutionPlanError(
            "target account or region changed after approval: "
            f"{plan.account_id}/{plan.region} → {account_id}/{region}"
        )
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
    current_diff = current_workspace_diff(root)
    if _sha256(current_diff) != plan.diff_sha256:
        raise ExecutionPlanError("working tree diff changed after approval")
    return plan


# Note: the remote-PR verification that used to live here moved into the
# deterministic execute (app.pr_execution._verify_remote_paths). It must run with
# the short-lived write grant in the environment so `gh` can authenticate — the
# worker process holds no GitHub credential — which is why it is no longer a
# separate worker postcondition step.
