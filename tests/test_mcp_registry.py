"""MCP registry lock — server source/config/tool inventory drift must fail CI."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from app.agent_monitor import MONITOR_TOOLS, mcp_config_json
from app.assistant_handler import ASSISTANT_TOOLS
from app.chat_agent import CHAT_TOOLS


_ROOT = Path(__file__).resolve().parents[1]


def _slackops_registry_entry() -> dict[str, object]:
    payload = json.loads((_ROOT / "deploy/mcp/registry.json").read_text())
    assert payload["version"] == 1
    assert len(payload["servers"]) == 1
    entry = payload["servers"][0]
    assert entry["name"] == "slackops"
    return entry


def test_internal_mcp_source_matches_reviewed_registry_hash() -> None:
    entry = _slackops_registry_entry()
    source = _ROOT / str(entry["source"])
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    assert digest == entry["sha256"], (
        "internal MCP source changed; review tool schema/credential scope and update "
        "deploy/mcp/registry.json intentionally"
    )


def test_registry_pins_stdio_command_and_proposal_only_tools() -> None:
    entry = _slackops_registry_entry()
    assert entry["transport"] == "stdio"
    assert entry["command"] == ["python", "-m", "app.mcp_server"]
    assert entry["tools"] == ["propose_job", "list_pending"]
    assert entry["credential_scope"] == "DynamoDB slackops-agent proposal queue only"
    assert entry["owner"] == "SlackOps platform"
    assert entry["reviewed_at"] == "2026-07-15"


def test_all_agent_mcp_tool_allowlists_match_registry_inventory() -> None:
    entry = _slackops_registry_entry()
    expected = {f"mcp__slackops__{tool}" for tool in entry["tools"]}
    assert set(MONITOR_TOOLS) == expected
    assert set(CHAT_TOOLS) == expected
    assert set(ASSISTANT_TOOLS) == expected


def test_runtime_mcp_config_matches_registry_command() -> None:
    entry = _slackops_registry_entry()
    payload = json.loads(mcp_config_json())
    server = payload["mcpServers"]["slackops"]
    assert [server["command"], *server["args"]] == entry["command"]
    # Static credential only: the MCP child must never fall back to IMDS.
    assert server["env"]["AWS_EC2_METADATA_DISABLED"] == "true"
