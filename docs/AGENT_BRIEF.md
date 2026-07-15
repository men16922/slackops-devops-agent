# AGENT_BRIEF — slackops-devops-agent
Last updated: 2026-07-16

> ▶ NEXT SESSION (**v2 AWSKRUG demo**): the secure-runtime bundle is **committed** (`3affc65`, `84535bc`, +D23) but
>   **not pushed** — main is ahead of origin. Next: push, then **slide finalization → live-demo rehearsal**
>   (plan: `docs/plans/2026-06-25-awskrug-demo.md`).
>   D19–D23 (2026-07-16) closed the Notion-reference P0 pair + P1 aggregation/trajectory: PreToolUse `command_guard`
>   is now the execution boundary (measured: `--allowedTools` alone let `echo hi; whoami` run), PR write credentials
>   are minted per approval, capability is declared + risk-scored vs a ceiling, and the audit trail is a step tree
>   whose observed capability gates completion.
>   Manual remains: GitHub App registration + 4 SSM params + EC2 `pr` execute rehearsal; Slack App Message Shortcut
>   registration; Slack approver setup. Remaining `[auto]` work is thin — the P0/P1 reference items are closed.
>   Presentation:
>   `docs/presentation/PRESENTATION.md` + `docs/presentation/SlackOps DevOps Agent (Standalone).html`.
> 1-minute compact entry point (≤60 lines). Standards in harness/CORE_MANDATES.md; work authority is NEXT_PLAN.md > docs/plans/.

## Read Path (session start/resume)
harness/CONTEXT_BRIDGE.md → docs/AGENT_BRIEF.md → docs/STATUS.md → docs/NEXT_PLAN.md
→ (if needed) top of docs/PROGRESS_LOG.md → (if needed) docs/archive/

## Snapshot
- **What:** Slack natural-language command → Claude Code Headless on EC2 analyzes AWS/K8s/Terraform/GitHub context → ops automation.
  MVP = Read-Only analysis + PR creation.
- **Differentiator:** Not just a bot but a reference for "how to run an agent safely" — security (permissions + injection defense) + observability (OTel).
- **Behavior:** command routing (ping/logs/diagnose registered) + job queue + permission gate + sanitizer
  + claude_runner + allowlist (run_for_command single entry point) + logs/diagnose handlers (fetcher
  inject→isolate→assemble; diagnose is multi-source + per-source failure isolation) + store/ (H0 single-table —
  Job/Audit/Telemetry each with Sqlite+DynamoDb implementations) + telemetry (record_run_metrics→
  inject store, OTel is a lazy stub) + worker (polling consumer — claim→run→output-gate/
  complete + audit/metric write-back) + tf-review (plan-isolated review, no apply path)
  + pr (2-stage output gate — prepare strips push/PR tool argv + extracts diff, execute runs
  only after approval) — locally verified. AWS/Slack execution prep is in deploy/. **web/ dashboard (Next.js)**
  = jobs feed/detail (diff output gate + Approve/Reject)/metrics, DynamoDB Local offline docker (port
  8930) local e2e verified. DDB_ENDPOINT toggle switches to real DynamoDB (Vercel) (D7). Inference = subscription OAuth (D6).
  + **agent autonomous proposal (D9)** — mcp_server (propose_job MCP) + agent_monitor (Tier1 simulator/Tier2 claude -p):
  agent proposes to the queue → human approval via the existing output gate. JobSource.AGENT + Job.rationale.
  Runbook docs/runbooks/agent-mcp-demo.md.
  + **conversational producer (D10)** — natural-language chat over a DynamoDB conversation bus (chat_store, GSI1) +
  chat_agent polling consumer + web Chat. Agent inbound = 0 (poll-only) → works on Vercel. Real Claude e2e verified.
- **Verification:** 3-layer gate — `make check` (540 passed) + ruff + mypy (strict) + documentation budget.
  web/ is `next build` + `docker compose up` e2e green. **`make demo`** runs the full local stack (web+DB+chat_agent+worker) in one shot.
- **Current focus:** cloud deploy A–C verified (DynamoDB us-east-1 live, EC2 ping pong, then terminated). Logs/diagnose/detect use fixed read adapters → sanitizer isolation (generic AWS MCP retired). D17/P1/P2 fresh EC2 rehearsal verified role/credential/egress/audit boundaries plus deterministic scope deny before fetch and Worker audit; instance stopped. P3 is local/CI-only separate-account managed-MCP scaffolding, not an enabled AWS integration.

## Guardrails summary (details in CORE_MANDATES)
- Socket Mode only (no inbound port). IAM Instance Profile only (no Access Key).
- Only permission L0/1 active, L2 (Execute) disabled. No Production/deploy/IAM/DB changes.
- 4-layer injection defense: Sanitizer / Tool Allowlist / output gate / Template Prompt.
- EC2 runs on EventBridge schedule (never always-on).

## Slack commands (MVP)
- `/devops ping` — health check
- `/devops logs <service>` — CloudWatch query + analysis
- `/devops diagnose <service>` — CloudWatch + kubectl + git diff combined diagnosis
- `/devops tf-review` — terraform plan risk/cost/security review
- `/devops pr <description>` — branch → modify → test → PR (human-confirmation gate)

## Slash commands (work harness)
- `/sync` — at session start/resume, read only the Read Path and summarize (read-only)
- `/checkpoint` — on work-bundle completion, append PROGRESS_LOG + conditional updates (record-only)
- `/tidy-docs` — when docs bloat, split/compress/consolidate into archive (tidy-only)
