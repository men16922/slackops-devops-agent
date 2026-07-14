"""Versioned adversarial corpus for prompt isolation and approval integrity."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from app.commands.detect import build_detect_prompt
from app.commands.diagnose import build_diagnose_prompt
from app.commands.logs import build_logs_prompt
from app.commands.tf_review import build_tf_review_prompt
from app.execution_plan import ExecutionPlanError, build_pr_plan, changed_paths, verify_pr_workspace
from app.sanitizer import UNTRUSTED_CLOSE, UNTRUSTED_OPEN


_ROOT = Path(__file__).resolve().parents[1]
_CASES: dict[str, list[dict[str, str]]] = json.loads(
    (_ROOT / "tests/security_corpus/agent_security_cases.json").read_text()
)


def _prompt_builders(payload: str) -> list[str]:
    return [
        build_logs_prompt("checkout", payload),
        build_diagnose_prompt("checkout", [("cloudwatch", payload)]),
        build_detect_prompt("iam", payload),
        build_tf_review_prompt(payload),
    ]


@pytest.mark.parametrize("case", _CASES["prompt_injection"], ids=lambda item: item["id"])
def test_injection_corpus_stays_inside_one_untrusted_boundary(case: dict[str, str]) -> None:
    marker = case["id"]
    payload = f"case={marker}\n{case['payload']}"
    for prompt in _prompt_builders(payload):
        assert prompt.count(UNTRUSTED_OPEN) == 1
        assert prompt.count(UNTRUSTED_CLOSE) == 1
        open_index = prompt.index(UNTRUSTED_OPEN)
        close_index = prompt.index(UNTRUSTED_CLOSE)
        assert open_index < prompt.index(marker) < close_index
        # A forged structural tag must not appear raw inside the data block.
        body = prompt[open_index + len(UNTRUSTED_OPEN) : close_index]
        assert "<untrusted_data" not in body.lower()
        assert "</untrusted_data" not in body.lower()


@pytest.mark.parametrize("case", _CASES["approval_integrity"][:2], ids=lambda item: item["id"])
def test_approval_corpus_rejects_unsafe_diff_paths(case: dict[str, str]) -> None:
    with pytest.raises(ExecutionPlanError, match="unsafe diff path"):
        changed_paths(case["diff"])


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


def test_approval_corpus_rejects_untracked_post_approval_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    case = _CASES["approval_integrity"][2]
    root = _repository(tmp_path)
    (root / "service.txt").write_text("after\n", encoding="utf-8")
    _git(root, "add", "service.txt")
    diff = _git(root, "diff", "HEAD", "--no-ext-diff", "--binary")
    monkeypatch.setenv("SLACKOPS_WORKSPACE_ROOT", str(root))
    plan = build_pr_plan("update service", diff)

    (root / case["path"]).write_text(case["content"], encoding="utf-8")
    with pytest.raises(ExecutionPlanError, match="untracked files"):
        verify_pr_workspace("update service", diff, plan.canonical_json(), plan.digest())
