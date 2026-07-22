"""P2 deterministic account/region/resource/time-window policy tests."""

from __future__ import annotations

import pytest

from app.commands.logs import handle_logs
from app.policy_boundary import PolicyDenied, authorize_command, scope_for_command
from tests._helpers import RecordingFetcher, RecordingRunner


_STRICT_ENV = {
    "SLACKOPS_POLICY_ENFORCEMENT": "true",
    "AWS_ACCOUNT_ID": "123456789012",
    "AWS_REGION": "us-east-1",
    "SLACKOPS_ALLOWED_AWS_ACCOUNT_IDS": "123456789012",
    "SLACKOPS_ALLOWED_AWS_REGIONS": "us-east-1",
    "SLACKOPS_ALLOWED_LOG_GROUP_PREFIXES": "/aws/lambda/,/aws/ecs/",
    "SLACKOPS_POLICY_WORKSPACE_ROOT": "/workspace/slackops",
}


@pytest.mark.parametrize(
    ("command", "argument", "resource", "window"),
    [
        ("ping", "", "local:health", 30),
        ("logs", "/aws/lambda/payments", "log_group:/aws/lambda/payments", 86400),
        ("diagnose", "/aws/ecs/payments", "log_group:/aws/ecs/payments", 86400),
        ("detect", "config", "detection:config", 86400),
        ("tf-review", "", "workspace:/workspace/slackops", 120),
        ("pr", "ignored-by-scope", "workspace:/workspace/slackops", 300),
    ],
)
def test_each_command_has_a_fixed_allowed_scope(
    command: str, argument: str, resource: str, window: int
) -> None:
    scope = authorize_command(command, argument, _STRICT_ENV)
    assert scope.account_id == "123456789012"
    assert scope.region == "us-east-1"
    assert scope.resource == resource
    assert scope.time_window_s == window


def test_missing_account_allowlist_fails_closed() -> None:
    env = {key: value for key, value in _STRICT_ENV.items() if key != "SLACKOPS_ALLOWED_AWS_ACCOUNT_IDS"}
    with pytest.raises(PolicyDenied, match="missing_allowed_accounts"):
        authorize_command("logs", "/aws/lambda/payments", env)


def test_user_argument_cannot_expand_log_group_scope() -> None:
    allowed = authorize_command("logs", "/aws/lambda/payments", _STRICT_ENV)
    assert allowed.resource == "log_group:/aws/lambda/payments"
    with pytest.raises(PolicyDenied, match="resource_not_allowed"):
        authorize_command("logs", "/secrets/other-team", _STRICT_ENV)


def test_fixed_time_window_cannot_be_replaced_by_a_caller() -> None:
    scope = scope_for_command("logs", "/aws/lambda/payments", _STRICT_ENV)
    forged = type(scope)(
        command=scope.command,
        account_id=scope.account_id,
        region=scope.region,
        resource=scope.resource,
        time_window_s=scope.time_window_s + 1,
    )
    from app.policy_boundary import enforce_scope

    with pytest.raises(PolicyDenied, match="time_window_not_allowed"):
        enforce_scope(forged, _STRICT_ENV)


def test_logs_handler_denies_before_fetch_when_scope_is_outside_policy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SLACKOPS_POLICY_ENFORCEMENT", "true")
    for key, value in _STRICT_ENV.items():
        monkeypatch.setenv(key, value)
    fetcher = RecordingFetcher()
    runner = RecordingRunner()

    reply = handle_logs("payments-api", fetcher=fetcher, runner=runner)

    assert reply.startswith(":no_entry:")
    assert fetcher.calls == []
    assert runner.calls == []


# Production EC2 config (deploy/ec2/user-data.sh): the reviewed prefix is exactly "/aws/".
# The LIVE ① demo depends on this: the seeded /aws/slackops-demo/... group is inside scope,
# while a bare service name is denied *before* any fetch (resource_not_allowed).
_PROD_ENV = {
    "SLACKOPS_POLICY_ENFORCEMENT": "true",
    "AWS_ACCOUNT_ID": "908601828278",
    "AWS_REGION": "us-east-1",
    "SLACKOPS_ALLOWED_AWS_ACCOUNT_IDS": "908601828278",
    "SLACKOPS_ALLOWED_AWS_REGIONS": "us-east-1",
    "SLACKOPS_ALLOWED_LOG_GROUP_PREFIXES": "/aws/",
}


def test_live_demo_log_group_is_inside_the_prod_aws_prefix() -> None:
    scope = authorize_command(
        "diagnose", "/aws/slackops-demo/checkout-service", _PROD_ENV
    )
    assert scope.resource == "log_group:/aws/slackops-demo/checkout-service"


def test_bare_service_name_is_denied_under_the_prod_aws_prefix() -> None:
    # Reproduces the LIVE blocker: "checkout-service" does not start with "/aws/".
    with pytest.raises(PolicyDenied, match="resource_not_allowed"):
        authorize_command("diagnose", "checkout-service", _PROD_ENV)
