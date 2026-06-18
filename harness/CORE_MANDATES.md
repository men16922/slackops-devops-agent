# CORE_MANDATES — slackops-devops-agent
Last updated: 2026-06-11

> Slowly-changing invariant standards only. For current work context use CONTEXT_BRIDGE.md / docs/.

## 1. Runtime Principles
- Language: Python 3.11+. **Single resident EC2 service** (not Lambda/serverless).
- Slack: **Bolt Socket Mode**. No inbound HTTP endpoint / public HTTPS / ALB / certificate — **forbidden**.
- LLM execution: invoke **Claude Code Headless** (subprocess). Don't build a direct model SDK wrapper (Bedrock/OpenAI).
- Job queue: **SQLite (MVP only)**. Don't refer to it as a prod datastore.
- Layers: separate slack_handler / permissions / sanitizer / claude_runner / telemetry / commands.

## 2. Security (differentiator — strict)
- **IAM Instance Profile only.** Never store/commit an Access Key.
- Least-privilege, read-only by default: CloudWatch RO, Logs RO, EKS Describe, SSM Read, S3 Read.
- Permission Engine Level 0/1/2. **MVP enables only 0·1; 2 (Execute) is disabled.**
- Hard invariants (forbidden): Production changes, deploys (apply/deploy), IAM changes, DB changes.
- GitHub: GitHub App with minimal scopes + branch protection (block auto-merge of agent PRs).
- Prompt Injection — 4 layers: ① Context Sanitizer (`<untrusted_data>` isolation) ② Tool Allowlist (per command)
  ③ output gate (L1 writes post the diff to Slack first, then require human confirmation) ④ enforced template prompt (never pass Slack input directly).

## 3. Observability
- OTel SDK → ADOT Collector → CloudWatch. Per run, instrument step latency / tokens / cost (USD) /
  tool call count·type·failure rate / E2E p50·p95.

## 4. Cost / Ops
- Stop/start EC2 on an EventBridge schedule. No always-on operation.

## 5. Code & Test Discipline
- Type hints required, `from __future__ import annotations`, `X | None`.
- Logging via structlog (or an OTel-integrated logger). No `print`. No bare `except` / `except: pass`.
- After multi-file changes, run the full `pytest` and report pass/fail. Don't declare "done" before it passes.
- Check `pyproject.toml` first for any new dependency.

## 6. Documentation & Handoff
- Read Path: CONTEXT_BRIDGE → AGENT_BRIEF → STATUS → NEXT_PLAN → (if needed) PROGRESS_LOG.
- No bulk-read of docs/. Update current docs via /checkpoint, read via /sync, tidy via /tidy-docs.
- New global (invariant) rules go in this file. No guessing (if it's not documented, say "not in the docs").
- Korean body + English identifiers/commands/paths.

## 7. Navigation tooling discipline (optional accelerator — Quarkify)
- Code exploration follows a **measured conditional policy** — for large packages / high-frequency symbols (broad searches), prefer the `.quarkify/src`
  index (regenerate with `make quarkify` when needed, idempotent ~seconds); for rare literals / small files, use grep.
  *(This repo is small (~3.6K LOC) — grep-first is the default for everyday exploration; use the index only for broad symbol searches.)*
- The index is **for locating only; final confirmation is the original file** (quark leaves are empty folders, no line numbers).
- It's an optional local accelerator, so **don't gate on it** (not part of `make check` — don't make the build depend on an absent artifact).
- Details: entry point CLAUDE.md "## Quarkify" section.
