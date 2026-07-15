"""P3 pilot scaffold must stay isolated from the default SlackOps runtime."""

from __future__ import annotations

import json
from pathlib import Path


_ROOT = Path(__file__).resolve().parents[1]
_PILOT = _ROOT / "deploy" / "mcp" / "managed-aws-pilot"


def _json(name: str) -> dict[str, object]:
    return json.loads((_PILOT / name).read_text())


def test_pilot_contract_requires_an_account_and_identity_boundary() -> None:
    boundary = _json("pilot-boundary.json")
    assert boundary["runtimeAccountId"] != boundary["pilotAccountId"]
    assert boundary["managedMcpServer"] == "aws-mcp.amazonaws.com"
    assert boundary["pilotRoleName"] == "slackops-managed-aws-mcp-pilot-role"
    forbidden = set(boundary["forbiddenRuntimeRoles"])  # type: ignore[arg-type]
    assert "slackops-devops-agent-runtime-role" in forbidden
    assert "slackops-devops-agent-mcp-role" in forbidden


def test_pilot_policy_is_logs_read_only_and_bound_to_aws_managed_mcp() -> None:
    policy = _json("pilot-role-policy.json")
    allow = next(
        statement
        for statement in policy["Statement"]  # type: ignore[index]
        if statement["Sid"] == "AllowApprovedLogsReadOnlyViaAwsManagedMcp"  # type: ignore[index]
    )
    assert set(allow["Action"]) == {  # type: ignore[index]
        "logs:DescribeLogStreams",
        "logs:GetLogEvents",
        "logs:FilterLogEvents",
    }
    assert all("__LOG_GROUP_PREFIX__" in resource for resource in allow["Resource"])  # type: ignore[index]
    condition = allow["Condition"]  # type: ignore[index]
    assert condition["Bool"]["aws:ViaAWSMCPService"] == "true"  # type: ignore[index]
    assert condition["StringEquals"]["aws:CalledViaAWSMCP"] == "aws-mcp.amazonaws.com"  # type: ignore[index]

    deny = next(
        statement
        for statement in policy["Statement"]  # type: ignore[index]
        if statement["Sid"] == "DenyMutationInPilotEvenIfAnotherPolicyIsAdded"  # type: ignore[index]
    )
    denied = set(deny["Action"])  # type: ignore[index]
    assert {"logs:PutLogEvents", "logs:DeleteLogGroup", "iam:*", "sts:AssumeRole"} <= denied


def test_pilot_evidence_query_flags_identity_scope_and_read_only_drift() -> None:
    query = (_PILOT / "cloudtrail-lake-violations.sql").read_text()
    for expected in (
        "eventType = 'AwsMcpEvent'",
        "recipientAccountId <> '__PILOT_ACCOUNT_ID__'",
        "awsRegion <> '__PILOT_REGION__'",
        "__PILOT_ROLE_NAME__",
        "readOnly <> true",
        "eventSource NOT LIKE 'aws-mcp.%'",
    ):
        assert expected in query


def test_default_runtime_does_not_reference_the_pilot_or_managed_aws_mcp() -> None:
    runtime_deploy = "\n".join(
        path.read_text() for path in (_ROOT / "deploy" / "ec2").glob("*") if path.is_file()
    )
    assert "slackops-managed-aws-mcp-pilot-role" not in runtime_deploy
    assert "aws-mcp.amazonaws.com" not in runtime_deploy
