# AGENT_BRIEF — slackops-devops-agent
Last updated: 2026-07-15

> ▶ NEXT SESSION (**v2 AWSKRUG demo**): commit/push the D16–D17 + P1 secure-runtime/rehearsal bundle, then add a
>   P2 deterministic policy interceptor before **slide finalization → live-demo rehearsal**. D17/P1 new-EC2 runtime
>   boundaries and central audit evidence were verified; the rehearsal instance stopped. Slack approver setup remains manual.
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
  + **agent autonomous proposal (D9)** — mcp_server (propose_job MCP) + agent_monitor (Tier1 simulator/Tier2
  claude -p): agent proposes to the queue → human approval via the existing output gate. web has a human producer (chat/selectbox)
  + agent badge/rationale. JobSource.AGENT + Job.rationale. Runbook docs/runbooks/agent-mcp-demo.md.
  + **conversational producer (D10)** — selectbox→natural-language chat. DynamoDB conversation bus (chat_store, GSI1 overloading)
  + claude_runner streaming (stream-json) + chat_agent polling consumer + web Chat (polling Markdown render). Agent
  inbound = 0 (poll-only) → works on Vercel. Real Claude e2e verified. (Also includes web result Markdown render, Quarkify, worker entry.)
- **Verification:** 3-layer gate — `make check` (392 passed) + ruff + mypy (strict) + documentation budget.
  web/ is `next build` + `docker compose up` e2e green. **`make demo`** runs the full local stack (web+DB+chat_agent+worker) in one shot.
- **Current focus:** cloud deploy A–C verified (DynamoDB us-east-1 live, EC2 ping pong, then terminated). Logs/diagnose/detect now use fixed AWS read adapters → sanitizer isolation (generic AWS MCP retired). D17/P1 fresh EC2 rehearsal verified role/credential/egress boundaries plus central audit `credential_refresh` and URL-free `proxy_denied` evidence; instance stopped.

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
