"""capability taxonomy + risk 집계 + 재승인 트리거.

개별 도구가 안전해 보여도 한 Job 안의 도구들이 **누적**되면 권한이 결합된다
(multi-tool composition). 여기서 검증하는 것은 그 누적을 과소평가하지 않는 것,
그리고 승인 이후 무언가 달라지면 실행이 아니라 거부로 끝나는 것이다.
"""

from __future__ import annotations

import pytest

from app import allowlist
from app.execution_plan import (
    PRIVILEGED,
    READ,
    RISK_CEILING,
    WRITE_HIGH,
    WRITE_LOW,
    ExecutionPlanError,
    build_pr_plan,
    capabilities_for_tools,
    declared_tools,
    risk_score,
)


class TestTaxonomy:
    def test_every_allowlisted_tool_is_classified(self) -> None:
        # 분류가 없는 도구는 risk 집계에서 0 으로 빠져 누적 위험을 감춘다.
        used = {t for cmd in allowlist.known_commands() for t in allowlist.allowed_tools(cmd)}
        assert used <= declared_tools()

    @pytest.mark.parametrize(
        ("tool", "capability"),
        [
            # 과거 substring 휴리스틱이 전부 '분류 없음'으로 흘려보내던 도구들.
            ("Bash(git add:*)", WRITE_LOW),
            ("Bash(git checkout:*)", WRITE_LOW),
            ("Bash(python -m pytest:*)", WRITE_LOW),
            ("Bash(terraform plan:*)", READ),
            ("Bash(terraform show:*)", READ),
        ],
    )
    def test_previously_unclassified_tools_now_carry_capability(
        self, tool: str, capability: str
    ) -> None:
        assert capabilities_for_tools((tool,)) == (capability,)

    def test_unknown_tool_fails_closed(self) -> None:
        with pytest.raises(ExecutionPlanError, match="no declared capability"):
            capabilities_for_tools(("Bash(curl:*)",))

    def test_unknown_capability_fails_closed(self) -> None:
        with pytest.raises(ExecutionPlanError, match="unknown capability"):
            risk_score(("teleport",))


class TestRiskAggregation:
    def test_risk_sums_across_the_chain(self) -> None:
        # 체인 전체를 합산한다 — 가장 위험한 도구 하나로 갈음하지 않는다.
        assert risk_score((READ,)) == 1
        assert risk_score((READ, WRITE_LOW)) == 6
        assert risk_score((READ, WRITE_LOW)) > risk_score((WRITE_LOW,))

    def test_pr_chain_is_under_the_ceiling(self) -> None:
        tools = tuple(sorted(allowlist.allowed_tools("pr")))
        assert risk_score(capabilities_for_tools(tools)) <= RISK_CEILING

    @pytest.mark.parametrize("capability", [WRITE_HIGH, PRIVILEGED])
    def test_write_high_and_privileged_exceed_the_ceiling_alone(self, capability: str) -> None:
        # "L2 비활성 + privileged 차단"이 특례 목록이 아니라 하나의 산술 규칙이 된다.
        assert risk_score((capability,)) > RISK_CEILING


class TestPlanBuildCeiling:
    def test_over_ceiling_plan_is_never_offered_for_approval(
        self, tmp_path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import subprocess

        subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
        monkeypatch.setattr(
            "app.execution_plan._TOOL_CAPABILITIES",
            {"Bash(danger:*)": PRIVILEGED, "Read": READ},
        )
        diff = "--- a/x.py\n+++ b/x.py\n"
        with pytest.raises(ExecutionPlanError, match="exceeds the ceiling"):
            build_pr_plan(
                "desc",
                diff,
                workspace_root=tmp_path,
                execution_tools=("Read", "Bash(danger:*)"),
            )

    def test_plan_pins_score_ceiling_and_target(self, tmp_path) -> None:
        import subprocess

        subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
        plan = build_pr_plan(
            "desc",
            "--- a/x.py\n+++ b/x.py\n",
            workspace_root=tmp_path,
            execution_tools=("Read", "Bash(git push:*)"),
            account_id="111122223333",
            region="us-east-1",
        )
        assert plan.capabilities == (READ, WRITE_LOW)
        assert plan.risk_score == 6
        assert plan.risk_ceiling == RISK_CEILING
        assert plan.account_id == "111122223333"
        # 이 값들은 해시에 들어간다 — 바뀌면 승인 자체가 무효가 된다.
        assert "risk_score" in plan.canonical_json()
        assert "111122223333" in plan.canonical_json()
