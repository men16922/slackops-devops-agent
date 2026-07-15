"""Squid egress allowlist regression tests."""
from __future__ import annotations

from pathlib import Path


_CONFIG = (
    Path(__file__).resolve().parents[1] / "deploy" / "ec2" / "egress-proxy.conf"
)


def test_allowed_domain_acl_has_no_redundant_subdomains() -> None:
    """Squid 6 rejects an ACL containing both a domain and its subdomain."""
    line = next(
        entry
        for entry in _CONFIG.read_text().splitlines()
        if entry.startswith("acl slackops_allowed dstdomain ")
    )
    domains = line.split()[3:]

    for domain in domains:
        assert not any(
            parent != domain and parent.startswith(".") and domain.endswith(parent)
            for parent in domains
        ), f"redundant Squid domain ACL: {domain} is already covered"
