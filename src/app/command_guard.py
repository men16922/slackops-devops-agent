"""Deterministic argv guard for every Bash tool call the model makes.

``--allowedTools`` alone does not bound execution.  Measured against Claude Code
2.1.210: ``--allowedTools 'Bash(echo:*)'`` still executes ``echo hi; whoami`` —
the pattern matches the head of the command line, so any chained, substituted or
redirected command rides along with an allowlisted prefix.

This module closes that hole at the tool boundary.  It is installed as a
``PreToolUse`` hook (see :func:`hook_settings_json`); a ``deny`` decision from the
hook overrides the ``--allowedTools`` allow, so every Bash command is normalized
and matched against a per-command argument schema before it can run.  The model
never reaches a shell that we have not parsed ourselves.

Nothing here consults the model, the prompt, or Slack input: the schema set is
fixed in code and selected by the trusted command name that the runtime places in
``SLACKOPS_GUARD_COMMAND``.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

# The command whose schema set applies to this Claude process. Set by the runtime
# (claude_runner), never by the model — a Bash subshell cannot alter the env of
# the parent claude process that spawns the hook.
GUARD_COMMAND_ENV = "SLACKOPS_GUARD_COMMAND"

# Shell constructs that turn one allowlisted command into arbitrary execution.
# Rejected before parsing: command separators, substitution, redirection, globs,
# expansion and escapes. Quotes survive so that `git commit -m "text"` is usable.
_FORBIDDEN_CHARS: frozenset[str] = frozenset(";&|<>`$(){}[]*?~!\\\n\r\t\x00")

_BRANCH_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,99}$")
_REPO_PATH_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,199}$")
_TEXT_RE = re.compile(r"^[^\x00-\x1f]{1,2000}$")


class CommandGuardError(Exception):
    """A Bash command failed deterministic normalization or schema validation."""


@dataclass(frozen=True)
class ArgSchema:
    """The complete shape of one permitted command line.

    Attributes:
        prefix: fixed leading tokens (binary plus subcommand) that must match exactly.
        flags: permitted flags mapped to whether the flag consumes a value.
        positional: pattern every positional argument must satisfy; None forbids
            positional arguments entirely.
        max_positional: upper bound on positional arguments.
    """

    prefix: tuple[str, ...]
    flags: Mapping[str, bool] = field(default_factory=dict)
    positional: re.Pattern[str] | None = None
    max_positional: int = 0


def _schema(
    prefix: str,
    *,
    flags: Mapping[str, bool] | None = None,
    positional: re.Pattern[str] | None = None,
    max_positional: int = 0,
) -> ArgSchema:
    return ArgSchema(
        prefix=tuple(prefix.split()),
        flags=flags or {},
        positional=positional,
        max_positional=max_positional,
    )


# Per-command schema sets. These mirror app.allowlist._COMMAND_TOOLS but bound the
# argv itself rather than the tool-pattern prefix. Commands whose tool allowlist is
# empty (logs/diagnose/detect — app-side fixed read adapters) get no Bash surface.
_COMMAND_SCHEMAS: dict[str, tuple[ArgSchema, ...]] = {
    "logs": (),
    "detect": (),
    "diagnose": (),
    "tf-review": (
        _schema("terraform plan", flags={"-no-color": False, "-input": True}),
        _schema("terraform show", flags={"-no-color": False, "-json": False}),
    ),
    "pr": (
        _schema("git status", flags={"--porcelain": False, "--short": False}),
        _schema(
            "git diff",
            flags={
                "--no-ext-diff": False,
                "--binary": False,
                "--staged": False,
                "--cached": False,
                "--stat": False,
            },
            positional=_REPO_PATH_RE,
            max_positional=1,
        ),
        _schema("git checkout -b", positional=_BRANCH_RE, max_positional=1),
        _schema("git add", flags={"-A": False, "--all": False}, positional=_REPO_PATH_RE, max_positional=50),
        _schema("git commit", flags={"-m": True, "--message": True}),
        _schema(
            "git push",
            flags={"-u": False, "--set-upstream": False},
            positional=_BRANCH_RE,
            max_positional=2,
        ),
        _schema(
            "gh pr create",
            flags={
                "--title": True,
                "--body": True,
                "--base": True,
                "--head": True,
                "--draft": False,
            },
        ),
        _schema(
            "python -m pytest",
            flags={"-q": False, "--quiet": False, "-x": False, "--tb": True},
            positional=_REPO_PATH_RE,
            max_positional=20,
        ),
    ),
}


def known_commands() -> frozenset[str]:
    """Commands that have a guard schema set (mirrors the tool allowlist)."""
    return frozenset(_COMMAND_SCHEMAS)


def normalize(command_line: str) -> tuple[str, ...]:
    """Reject shell metacharacters, then split into argv.

    Normalization happens before any policy decision, so a schema never sees a
    string whose meaning depends on shell evaluation.

    Raises:
        CommandGuardError: on empty input, a forbidden construct, a parent-directory
            traversal, or an unparsable quoting.
    """
    if not command_line.strip():
        raise CommandGuardError("empty command")
    found = sorted(_FORBIDDEN_CHARS.intersection(command_line))
    if found:
        raise CommandGuardError(
            f"forbidden shell construct in command: {''.join(found)!r}"
        )
    try:
        argv = shlex.split(command_line)
    except ValueError as exc:
        raise CommandGuardError(f"unparsable command: {exc}") from None
    if not argv:
        raise CommandGuardError("empty command")
    for token in argv:
        if token == ".." or token.startswith("../") or "/../" in token or token.endswith("/.."):
            raise CommandGuardError(f"parent-directory traversal is not allowed: {token!r}")
        if token.startswith("/"):
            raise CommandGuardError(f"absolute path is not allowed: {token!r}")
    return tuple(argv)


def _match_schema(argv: tuple[str, ...], schema: ArgSchema) -> None:
    if argv[: len(schema.prefix)] != schema.prefix:
        raise CommandGuardError("command does not match schema prefix")
    rest = list(argv[len(schema.prefix) :])
    positionals = 0
    index = 0
    while index < len(rest):
        token = rest[index]
        if token.startswith("-"):
            name, _, inline = token.partition("=")
            if name not in schema.flags:
                raise CommandGuardError(f"flag is not allowed: {name!r}")
            takes_value = schema.flags[name]
            if inline:
                if not takes_value:
                    raise CommandGuardError(f"flag takes no value: {name!r}")
                if not _TEXT_RE.match(inline):
                    raise CommandGuardError(f"invalid value for {name!r}")
            elif takes_value:
                index += 1
                if index >= len(rest):
                    raise CommandGuardError(f"flag requires a value: {name!r}")
                if not _TEXT_RE.match(rest[index]):
                    raise CommandGuardError(f"invalid value for {name!r}")
            index += 1
            continue
        positionals += 1
        if schema.positional is None or positionals > schema.max_positional:
            raise CommandGuardError(f"positional argument is not allowed: {token!r}")
        if not schema.positional.match(token):
            raise CommandGuardError(f"invalid positional argument: {token!r}")
        index += 1


def validate(command: str, command_line: str) -> tuple[str, ...]:
    """Return the normalized argv only if it matches a schema for ``command``.

    Args:
        command: the trusted subcommand name (logs/diagnose/detect/tf-review/pr).
        command_line: the raw Bash command string proposed by the model.

    Raises:
        CommandGuardError: unknown command (default deny), a forbidden shell
            construct, or no schema match.
    """
    try:
        schemas = _COMMAND_SCHEMAS[command]
    except KeyError:
        raise CommandGuardError(
            f"no command guard schema for command (default deny): {command!r}"
        ) from None
    argv = normalize(command_line)
    if not schemas:
        raise CommandGuardError(f"command {command!r} may not run shell commands")
    errors: list[str] = []
    for schema in schemas:
        try:
            _match_schema(argv, schema)
        except CommandGuardError as exc:
            errors.append(str(exc))
            continue
        return argv
    raise CommandGuardError(
        f"no allowed argument schema matches this command: {' '.join(argv)!r}"
    )


# ── PreToolUse hook ────────────────────────────────────────────────────────
# Contract measured against Claude Code 2.1.210: stdin carries
# {"hook_event_name","tool_name","tool_input":{"command":...},...}; a stdout
# payload of {"hookSpecificOutput":{"hookEventName":"PreToolUse",
# "permissionDecision":"deny"|"allow", ...}} with exit code 0 decides the call,
# and a deny overrides an --allowedTools allow.
_HOOK_EVENT = "PreToolUse"


def _decision(decision: str, reason: str) -> str:
    return json.dumps(
        {
            "hookSpecificOutput": {
                "hookEventName": _HOOK_EVENT,
                "permissionDecision": decision,
                "permissionDecisionReason": reason,
            }
        }
    )


def hook_decision(payload: Mapping[str, object], command: str | None) -> str:
    """Decide one PreToolUse event. Anything unrecognized fails closed."""
    if payload.get("tool_name") != "Bash":
        return _decision("allow", "not a shell command")
    if not command:
        return _decision("deny", "command guard is not configured for this runtime")
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return _decision("deny", "malformed tool input")
    command_line = tool_input.get("command")
    if not isinstance(command_line, str):
        return _decision("deny", "malformed shell command")
    try:
        validate(command, command_line)
    except CommandGuardError as exc:
        return _decision("deny", f"command guard: {exc}")
    return _decision("allow", "matches the approved argument schema")


def hook_settings_json(hook_command: Sequence[str]) -> str:
    """Build the ``--settings`` JSON that installs this guard as a PreToolUse hook.

    The guarded command name travels in ``SLACKOPS_GUARD_COMMAND`` rather than in
    this settings payload, so the schema selection stays in the process env that
    the model's Bash subshell cannot reach.
    """
    return json.dumps(
        {
            "hooks": {
                _HOOK_EVENT: [
                    {
                        "matcher": "Bash",
                        "hooks": [
                            {"type": "command", "command": shlex.join(hook_command)}
                        ],
                    }
                ]
            }
        }
    )


def main() -> None:
    """Hook entry point — ``python -m app.command_guard``."""
    try:
        payload = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, ValueError):
        sys.stdout.write(_decision("deny", "command guard received malformed hook input"))
        return
    if not isinstance(payload, dict):
        sys.stdout.write(_decision("deny", "command guard received malformed hook input"))
        return
    sys.stdout.write(hook_decision(payload, os.environ.get(GUARD_COMMAND_ENV)))


if __name__ == "__main__":
    main()
