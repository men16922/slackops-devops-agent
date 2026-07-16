"""배포 산출물의 agent runtime 보안 불변 회귀 테스트."""

from __future__ import annotations

import json
from pathlib import Path


_ROOT = Path(__file__).resolve().parents[1]
_USER_DATA = (_ROOT / "deploy/ec2/user-data.sh").read_text()
_REFRESH_SCRIPT = (_ROOT / "deploy/ec2/refresh-runtime-credentials.sh").read_text()
_EGRESS_PROXY = (_ROOT / "deploy/ec2/egress-proxy.conf").read_text()


def _unit_body(unit_name: str) -> str:
    marker = f"cat > /etc/systemd/system/{unit_name} <<'UNIT'\n"
    return _USER_DATA.split(marker, 1)[1].split("\nUNIT", 1)[0]


def _policy(name: str) -> dict[str, object]:
    return json.loads((_ROOT / "deploy/iam" / name).read_text())


def _actions(policy: dict[str, object]) -> set[str]:
    return {
        action
        for statement in policy["Statement"]  # type: ignore[index]
        for action in statement.get("Action", [])  # type: ignore[union-attr]
    }


def test_every_agent_service_has_the_host_runtime_boundary() -> None:
    expected = {
        "NoNewPrivileges=true",
        "PrivateTmp=true",
        "ProtectHome=read-only",
        "ProtectSystem=strict",
        "ReadWritePaths=/opt/slackops-devops-agent",
        "UMask=0077",
        "PrivateDevices=true",
        "ProtectClock=true",
        "ProtectControlGroups=true",
        "ProtectHostname=true",
        "ProtectKernelModules=true",
        "ProtectKernelTunables=true",
        "RestrictSUIDSGID=true",
        "LockPersonality=true",
        "ProtectProc=invisible",
        "ProcSubset=pid",
        "IPAddressDeny=169.254.169.254/32",
        "IPAddressDeny=any",
        "IPAddressAllow=127.0.0.1",
        "IPAddressAllow=::1",
        "EnvironmentFile=/etc/slackops-devops-agent.runtime.env",
        "ExecStartPre=+/usr/local/sbin/slackops-refresh-runtime-credentials",
    }
    units = (
        "slackops-devops-agent.service",
        "slackops-devops-agent-worker.service",
        "slackops-devops-agent-chat-agent.service",
        "slackops-devops-agent-monitor.service",
    )
    for unit in units:
        assert expected <= set(_unit_body(unit).splitlines()), unit


def test_bootstrap_policy_only_reads_boot_secrets_and_assumes_named_roles() -> None:
    policy = _policy("instance-profile-policy.json")
    assert _actions(policy) == {"ssm:GetParameter", "sts:AssumeRole"}
    statements = policy["Statement"]  # type: ignore[index]
    secret_read = next(item for item in statements if item["Sid"] == "BootstrapSecretRead")
    assert secret_read["Action"] == ["ssm:GetParameter"]
    assert all(
        resource.startswith("arn:aws:ssm::__ACCOUNT_ID__:parameter/slackops/")
        for resource in secret_read["Resource"]
    )
    assume = next(item for item in statements if item["Sid"] == "AssumeOnlySlackOpsRuntimeRoles")
    assert assume["Resource"] == [
        "arn:aws:iam::__ACCOUNT_ID__:role/slackops-devops-agent-runtime-role",
        "arn:aws:iam::__ACCOUNT_ID__:role/slackops-devops-agent-mcp-role",
        "arn:aws:iam::__ACCOUNT_ID__:role/slackops-devops-agent-audit-role",
    ]


def test_runtime_policy_has_no_bootstrap_secret_access() -> None:
    policy = _policy("runtime-role-policy.json")
    actions = _actions(policy)
    assert "ssm:GetParameter" not in actions
    assert {"logs:FilterLogEvents", "dynamodb:PutItem"} <= actions
    assert "sts:AssumeRole" not in actions
    rendered = json.dumps(policy)
    assert "/slackops/SLACK_BOT_TOKEN" not in rendered
    assert "slackops-devops-agent-mcp-role" not in rendered


def test_mcp_control_plane_policy_is_dynamodb_queue_only() -> None:
    policy = _policy("mcp-control-plane-policy.json")
    assert _actions(policy) == {
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:UpdateItem",
        "dynamodb:Query",
    }
    assert "slackops-agent" in json.dumps(policy)


def test_refresh_script_uses_short_lived_roles_and_writes_root_only_env() -> None:
    assert "aws sts assume-role" in _REFRESH_SCRIPT
    assert "--duration-seconds 3600" in _REFRESH_SCRIPT
    assert "AWS_EC2_METADATA_DISABLED=true" in _REFRESH_SCRIPT
    assert "SLACKOPS_MCP_AWS_ACCESS_KEY_ID" in _REFRESH_SCRIPT
    assert "chmod 600" in _REFRESH_SCRIPT
    assert "chown root:root" in _REFRESH_SCRIPT


def test_credential_refresh_timer_restarts_services_before_expiry() -> None:
    assert "OnUnitActiveSec=45min" in _USER_DATA
    assert "slackops-runtime-credentials-refresh.timer" in _USER_DATA
    assert "try-restart slackops-devops-agent.service" in _USER_DATA


def test_credential_refresh_timer_fires_early_at_boot() -> None:
    """배포 안정화 #2 — 첫 발화가 부팅 직후여야 초기 IAM 전파 지연에 갇힌 서비스를
    45분 대기 없이 정상 runtime role 로 수렴시킨다(45min 이면 부팅 미가동과 동일)."""
    assert "OnBootSec=2min" in _USER_DATA
    assert "OnBootSec=45min" not in _USER_DATA


def test_agent_egress_is_forced_through_localhost_allowlist_proxy() -> None:
    assert "dnf install -y git jq python3.11 python3.11-pip squid" in _USER_DATA
    assert "HTTP_PROXY=http://127.0.0.1:3128" in _USER_DATA
    assert "HTTPS_PROXY=http://127.0.0.1:3128" in _USER_DATA
    assert "systemctl enable --now squid" in _USER_DATA
    assert "http_port 127.0.0.1:3128" in _EGRESS_PROXY
    assert "http_access deny to_localhost" in _EGRESS_PROXY
    assert "http_access deny to_linklocal" in _EGRESS_PROXY
    assert "http_access allow localhost slackops_allowed" in _EGRESS_PROXY
    assert "http_access deny all" in _EGRESS_PROXY
    for domain in (".slack.com", ".anthropic.com", ".github.com", ".amazonaws.com"):
        assert domain in _EGRESS_PROXY
