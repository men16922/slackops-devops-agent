"""detect 명령 테스트 — 카테고리 검증 + agentic 프롬프트/도구 조립(실 claude 없음)."""

from __future__ import annotations

import pytest

from app.commands.detect import (
    DETECTION_CATEGORIES,
    InvalidCategory,
    build_detect_prompt,
    handle_detect,
    validated_category,
)
from app.mcp_config import AWS_MCP_TOOLS
from tests._helpers import RecordingRunner, result_json


def test_categories_are_the_four_wired() -> None:
    assert DETECTION_CATEGORIES == frozenset({"iam", "config", "ssm", "incident"})


def test_validated_category_normalizes() -> None:
    assert validated_category("  IAM ") == "iam"


def test_validated_category_rejects_unknown() -> None:
    with pytest.raises(InvalidCategory):
        validated_category("rm-rf")


def test_build_prompt_per_category_differs() -> None:
    assert "Access Analyzer" in build_detect_prompt("iam")
    assert "Config" in build_detect_prompt("config")
    assert "patch" in build_detect_prompt("ssm").lower()
    assert "alarms" in build_detect_prompt("incident").lower()


def test_handle_detect_runs_agentic_with_aws_mcp() -> None:
    runner = RecordingRunner(stdout=result_json("2 non-compliant resources"))
    out = handle_detect("config", runner=runner)
    assert out == "2 non-compliant resources"
    (cmd, _timeout) = runner.calls[0]
    assert "--mcp-config" in cmd
    assert "--strict-mcp-config" in cmd
    idx = cmd.index("--allowedTools")
    assert cmd[idx + 1 : idx + 1 + len(AWS_MCP_TOOLS)] == list(AWS_MCP_TOOLS)


def test_handle_detect_invalid_category_no_run() -> None:
    runner = RecordingRunner(stdout=result_json("should not run"))
    out = handle_detect("../etc", runner=runner)
    assert "categories:" in out
    assert runner.calls == []  # 검증 실패 → claude 미호출(default deny)
