"""Deterministic command scope policy at the runtime/tool boundary.

The model never selects an AWS account, region, resource, or time window.  Each
command receives a fixed scope before its adapter or executor starts; production
enables the boundary through root-owned systemd environment configuration.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


POLICY_ENFORCEMENT_ENV = "SLACKOPS_POLICY_ENFORCEMENT"
_ACCOUNT_ENV = "SLACKOPS_ALLOWED_AWS_ACCOUNT_IDS"
_REGION_ENV = "SLACKOPS_ALLOWED_AWS_REGIONS"
_LOG_PREFIX_ENV = "SLACKOPS_ALLOWED_LOG_GROUP_PREFIXES"
_WORKSPACE_ENV = "SLACKOPS_POLICY_WORKSPACE_ROOT"

# The time window is fixed in code, not accepted from Slack/model input.
_COMMAND_WINDOWS_S: dict[str, int] = {
    "ping": 30,
    "logs": 24 * 60 * 60,
    "diagnose": 24 * 60 * 60,
    "detect": 24 * 60 * 60,
    "tf-review": 2 * 60,
    "pr": 5 * 60,
}
_DETECTION_CATEGORIES = frozenset({"iam", "config", "ssm", "incident"})
_WORKSPACE_COMMANDS = frozenset({"tf-review", "pr"})
_LOG_COMMANDS = frozenset({"logs", "diagnose"})


class PolicyDenied(Exception):
    """A deterministic account/region/resource/time policy rejected a command."""

    def __init__(self, reason: str, scope: "CommandScope") -> None:
        super().__init__(f"policy denied: {reason}")
        self.reason = reason
        self.scope = scope


@dataclass(frozen=True)
class CommandScope:
    """Immutable scope resolved before data collection or execution."""

    command: str
    account_id: str
    region: str
    resource: str
    time_window_s: int

    def audit_context(self) -> dict[str, str]:
        return {
            "command": self.command,
            "account_id": self.account_id,
            "region": self.region,
            "resource": self.resource,
            "time_window_s": str(self.time_window_s),
        }


def _split(value: str | None) -> frozenset[str]:
    return frozenset(part.strip() for part in (value or "").split(",") if part.strip())


def enforcement_enabled(environ: Mapping[str, str] | None = None) -> bool:
    source = os.environ if environ is None else environ
    return source.get(POLICY_ENFORCEMENT_ENV, "false").lower() == "true"


def scope_for_command(
    command: str, argument: str = "", environ: Mapping[str, str] | None = None
) -> CommandScope:
    """Build a fixed command scope; unknown commands are immediately denied."""
    source = os.environ if environ is None else environ
    try:
        window = _COMMAND_WINDOWS_S[command]
    except KeyError:
        raise PolicyDenied(
            "unknown_command", CommandScope(command, "", "", "", 0)
        ) from None

    account = source.get("AWS_ACCOUNT_ID", "")
    region = source.get("AWS_REGION", source.get("AWS_DEFAULT_REGION", "us-east-1"))
    if command in _LOG_COMMANDS:
        resource = f"log_group:{argument}"
    elif command == "detect":
        resource = f"detection:{argument.lower()}"
    elif command in _WORKSPACE_COMMANDS:
        resource = f"workspace:{source.get(_WORKSPACE_ENV, source.get('SLACKOPS_WORKSPACE_ROOT', ''))}"
    else:
        resource = "local:health"
    return CommandScope(command, account, region, resource, window)


def enforce_scope(
    scope: CommandScope, environ: Mapping[str, str] | None = None
) -> CommandScope:
    """Fail closed in production when scope is not inside reviewed configuration.

    Local tests/demos remain explicitly non-enforcing unless
    ``SLACKOPS_POLICY_ENFORCEMENT=true`` is set.  EC2 user-data sets the value
    alongside the account, region, log-prefix, and workspace configuration.
    """
    source = os.environ if environ is None else environ
    if not enforcement_enabled(source):
        return scope

    accounts = _split(source.get(_ACCOUNT_ENV))
    if not accounts:
        raise PolicyDenied("missing_allowed_accounts", scope)
    if scope.account_id not in accounts:
        raise PolicyDenied("account_not_allowed", scope)

    regions = _split(source.get(_REGION_ENV))
    if not regions:
        raise PolicyDenied("missing_allowed_regions", scope)
    if scope.region not in regions:
        raise PolicyDenied("region_not_allowed", scope)

    expected_window = _COMMAND_WINDOWS_S.get(scope.command)
    if expected_window is None or scope.time_window_s != expected_window:
        raise PolicyDenied("time_window_not_allowed", scope)

    if scope.command in _LOG_COMMANDS:
        prefixes = _split(source.get(_LOG_PREFIX_ENV))
        name = scope.resource.removeprefix("log_group:")
        if not prefixes:
            raise PolicyDenied("missing_log_group_prefixes", scope)
        if not any(name.startswith(prefix) for prefix in prefixes):
            raise PolicyDenied("resource_not_allowed", scope)
    elif scope.command == "detect":
        category = scope.resource.removeprefix("detection:")
        if category not in _DETECTION_CATEGORIES:
            raise PolicyDenied("resource_not_allowed", scope)
    elif scope.command in _WORKSPACE_COMMANDS:
        configured = source.get(_WORKSPACE_ENV, source.get("SLACKOPS_WORKSPACE_ROOT", ""))
        expected = f"workspace:{Path(configured).resolve()}" if configured else ""
        actual = f"workspace:{Path(scope.resource.removeprefix('workspace:')).resolve()}" if scope.resource else ""
        if not configured or actual != expected:
            raise PolicyDenied("workspace_not_allowed", scope)
    return scope


def authorize_command(
    command: str, argument: str = "", environ: Mapping[str, str] | None = None
) -> CommandScope:
    """Build then enforce the only scope a command may use."""
    return enforce_scope(scope_for_command(command, argument, environ), environ)
