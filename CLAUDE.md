# CLAUDE.md — slackops-devops-agent
Last updated: 2026-06-17

> Harness entry rules. Design foundation: harness/CORE_MANDATES.md; current context: harness/CONTEXT_BRIDGE.md — consult these first.
> Run /sync at session start, /checkpoint when a work bundle completes, /tidy-docs when docs get bloated.
>   — Skills are provided by the **overnight-harness plugin** (repo-specific config in .claude/harness-config.json,
>     bible↔repo mapping in docs/engineering/interp/INTERPRETATION.md).
> Read Path: harness/CONTEXT_BRIDGE.md → docs/AGENT_BRIEF.md → docs/STATUS.md → docs/NEXT_PLAN.md.
> No bulk-read of all of docs/. Operating rules in docs/DOCS_POLICY.md. gate = `make check` (pytest+ruff+mypy+doc-budget).

- Communicate with the user in Korean; keep identifiers/commands/paths/code in English.
- Doc language: agent-only docs (entry docs, CLAUDE.md, harness/*, bibles, scripts/overnight/PROMPT.md) are in **English** (per-session token cost); user-facing/human-run docs (SLACK_GUIDE, DASHBOARD_GUIDE, QA_TEST, docs/runbooks/*, README) stay Korean. Entry-doc line caps enforced by `make check-doc-budget` (see DECISIONS D11).

---

## Project Overview

**One-liner:** Slack-controlled DevOps agent — turns Claude Code Headless into a remote operations engineer.
Differentiators: least-privilege security + prompt-injection defense + full OpenTelemetry instrumentation.

Slack natural-language command → Claude Code Headless on EC2 analyzes AWS/K8s/Terraform/GitHub context → ops automation.
MVP = **Read-Only analysis + PR creation**.

### Architecture
```
Slack (Socket Mode — no inbound port)
  ▼
EC2 DevOps Agent (c7i.large, started on an EventBridge schedule)
  ├── FastAPI + Slack Bolt (Socket Mode client)
  ├── Job Queue (SQLite — MVP only)
  ├── Permission Engine (Level 0/1/2)
  ├── Context Sanitizer            ← security
  ├── Claude Code Headless (AWS CLI/kubectl/terraform/gh/helm/jq, MCP)
  ├── OTel SDK → ADOT Collector    ← instrumentation
  └── IAM Instance Profile (no stored Access Key)
```

### Permission Model
| Level | Name | Allowed | MVP |
| --- | --- | --- | --- |
| 0 | Observe | logs/describe/get — read-only | ✅ |
| 1 | Prepare | branch, code modify, unit test, terraform plan, PR creation | ✅ |
| 2 | Execute | apply, rollout restart | ❌ disabled |

**Hard invariants (forbidden):** Production changes, deploys (apply/deploy), IAM changes, DB changes.

### Prompt Injection Defense — 4 layers
1. Context Sanitizer — inject logs/diffs isolated inside `<untrusted_data>` tags.
2. Tool Allowlist — predefined allowed tools per command.
3. Output gate — Level 1 writes (PR) post the diff to Slack first, then require human confirmation (branch protection).
4. Enforced template prompt — never pass Slack input directly.

### Slack Commands (MVP)
`/devops ping` · `/devops logs <service>` · `/devops diagnose <service>` · `/devops tf-review` · `/devops pr <description>`

---

## Development Guidelines
- For the invariant engineering standards see **harness/CORE_MANDATES.md** (runtime/security/observability/cost/code·test/docs).
- Essentials: Python 3.11+, Bolt Socket Mode only, Claude Code Headless subprocess, IAM Instance Profile only,
  type hints required, no `print`, run the full `python -m pytest tests/ -q` after multi-file changes and report.
- Non-goals / out-of-scope: see docs/STATUS.md Open Risks and BOOTSTRAP.md A8.

## Working Style (operating rules — from /insights)
- **Status questions:** for "status/progress" requests, read the **Read Path (/sync) and docs first**, before git/code exploration.
- **Overnight iteration:** one iteration = restore context (/sync) → **exactly one** `[auto]` → full `pytest` → /checkpoint
  → local commit. **Don't over-analyze commit strategy/scope — just commit.** Conventions in scripts/overnight/{run.sh,PROMPT.md}
  (runner: `make overnight` / one-shot `make overnight-once`).
- **Testing:** after multi-file changes, run the full `pytest` and **report the pass count** (e.g. "216 passed, 1 skipped").
- **Shell & verification:** use absolute paths; don't depend on state after `cd`. **Split compound bash (multi-stage `&&`/`;`) into separate steps**
  (avoids permission denials and debugging pain). Before committing, check with `git status` that the expected files are actually staged (guards against lost/interrupted writes).
- **Concise reporting:** keep status reports short/bulleted (avoid oversized output).

## Code navigation (LSP — preferred over grep for symbols)
Claude Code LSP (pyright) is the navigation tool. It returns line/kind/scope directly — no original re-read tax.
- **Definition / broad symbol search**: `LSP workspaceSymbol` (e.g. query `Store`) → exact `file:line` + kind (Class/Function/Variable) + parent scope.
- **Call graph**: `LSP incomingCalls` / `outgoingCalls` → caller fn + exact call site `line:col`.
- **References**: `LSP findReferences` is **type-aware** (the symbol, not the substring) — e.g. `JobStore` → 13 true refs vs grep's 36 substring hits (SqliteJobStore, comments, strings).
- **Bonus**: `hover` (types/docs), `goToImplementation`, live diagnostics on edited files.
- **When grep is still right**: rare string literals, config/log/non-Python files, whole-tree text patterns.
- **Measured (2026-06-19)**: LSP strictly dominated the retired Quarkify index on this repo (def / call-graph / references) — Quarkify removed (see DECISIONS, archive/quarkify-port.md).
