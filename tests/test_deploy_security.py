"""배포 산출물의 agent runtime 보안 불변 회귀 테스트."""

from __future__ import annotations

import json
from pathlib import Path


_ROOT = Path(__file__).resolve().parents[1]
_USER_DATA = (_ROOT / "deploy/ec2/user-data.sh").read_text()


def _unit_body(unit_name: str) -> str:
    marker = f"cat > /etc/systemd/system/{unit_name} <<'UNIT'\n"
    return _USER_DATA.split(marker, 1)[1].split("\nUNIT", 1)[0]


def test_every_agent_service_has_the_host_runtime_boundary() -> None:
    expected = {
        "NoNewPrivileges=true",
        "PrivateTmp=true",
        "ProtectHome=read-only",
        "ProtectSystem=strict",
        "ReadWritePaths=/opt/slackops-devops-agent",
        "UMask=0077",
    }
    units = (
        "slackops-devops-agent.service",
        "slackops-devops-agent-worker.service",
        "slackops-devops-agent-chat-agent.service",
        "slackops-devops-agent-monitor.service",
    )
    for unit in units:
        assert expected <= set(_unit_body(unit).splitlines()), unit


def test_instance_profile_has_no_unused_s3_read_access() -> None:
    policy = json.loads((_ROOT / "deploy/iam/instance-profile-policy.json").read_text())
    actions = {
        action
        for statement in policy["Statement"]
        for action in statement.get("Action", [])
    }
    assert not any(action.startswith("s3:") for action in actions)


def test_bootstrap_ssm_access_cannot_enumerate_or_read_arbitrary_parameters() -> None:
    policy = json.loads((_ROOT / "deploy/iam/instance-profile-policy.json").read_text())
    statement = next(item for item in policy["Statement"] if item["Sid"] == "SsmRead")
    assert statement["Action"] == ["ssm:GetParameter"]
    assert all(resource.startswith("arn:aws:ssm:*:*:parameter/slackops/") for resource in statement["Resource"])
