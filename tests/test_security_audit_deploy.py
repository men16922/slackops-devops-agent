"""Deployment guards for the root-only system-boundary audit sink."""

from __future__ import annotations

import json
from pathlib import Path


_ROOT = Path(__file__).resolve().parents[1]


def _policy(name: str) -> dict[str, object]:
    return json.loads((_ROOT / "deploy" / "iam" / name).read_text())


def test_bootstrap_can_assume_audit_role_and_runtime_explicitly_denies_sink_write() -> None:
    bootstrap = _policy("instance-profile-policy.json")
    statements = bootstrap["Statement"]
    assume = next(item for item in statements if item["Sid"] == "AssumeOnlySlackOpsRuntimeRoles")
    assert "arn:aws:iam::__ACCOUNT_ID__:role/slackops-devops-agent-audit-role" in assume["Resource"]

    audit = _policy("audit-role-policy.json")
    group = next(item for item in audit["Statement"] if item["Sid"] == "ReadSecurityBoundaryAuditStreamsOnly")
    write = next(item for item in audit["Statement"] if item["Sid"] == "WriteSecurityBoundaryAuditStreamsOnly")
    assert set(group["Action"]) == {
        "logs:DescribeLogStreams",
    }
    assert set(write["Action"]) == {
        "logs:CreateLogStream",
        "logs:PutLogEvents",
    }
    assert group["Resource"].endswith("log-group:/slackops/security-boundary-audit:*")
    assert write["Resource"].endswith("log-group:/slackops/security-boundary-audit:*")
    assert "logs:CreateLogGroup" not in json.dumps(audit)
    assert "logs:PutRetentionPolicy" not in json.dumps(audit)

    runtime = _policy("runtime-role-policy.json")
    deny = next(item for item in runtime["Statement"] if item["Sid"] == "DenySecurityBoundaryAuditWrite")
    assert deny["Effect"] == "Deny"
    assert set(deny["Action"]) == {
        "logs:CreateLogStream",
        "logs:PutLogEvents",
        "logs:PutRetentionPolicy",
    }
    assert "security-boundary-audit" in json.dumps(deny)

    mcp = (_ROOT / "deploy" / "iam" / "mcp-control-plane-policy.json").read_text()
    assert "security-boundary-audit" not in mcp


def test_audit_credentials_are_not_in_agent_service_environment() -> None:
    user_data = (_ROOT / "deploy" / "ec2" / "user-data.sh").read_text()
    assert "slackops-security-boundary-audit.env" not in user_data.split(
        "# --- credential rotation timer ---", maxsplit=1
    )[0]
    assert "install -d -o root -g root -m 700 /var/lib/slackops-security-audit" in user_data
    assert "User=root\nExecStart=/usr/local/sbin/slackops-security-audit-exporter" in user_data


def test_proxy_exporter_does_not_export_raw_requested_urls() -> None:
    exporter = (_ROOT / "deploy" / "ec2" / "audit-exporter.sh").read_text()
    assert "The deployment operator provisions the group and retention" in exporter
    assert "trap 'rm -f \"$event_file\"' RETURN" not in exporter
    assert 'rm -f "$event_file"' in exporter
    assert "Do not export the requested URL" in exporter
    assert 'emit "proxy_denied" "squid_status=$status"' in exporter
