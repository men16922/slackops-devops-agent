# AGENT_BRIEF — slackops-devops-agent
Last updated: 2026-07-17

> ▶ NEXT SESSION (**v2 AWSKRUG demo**): **The pr execute write path is FIXED and a real PR opened LIVE
>   (2026-07-17)** — Slack NL → agent propose → prepare(runtime diff) → dashboard approve(men16922) →
>   deterministic execute (`app.pr_execution.open_pr`, no LLM in the write path) → **GitHub PR #3 OPEN** →
>   job DONE. Three stacked root causes fixed: `ba813bf` (runtime diff as authoritative source),
>   `9081bed` (runtime-deterministic git plumbing), `be0422d` (grant-authed remote postcondition).
>   **Slack-native approval also verified LIVE**: Approve/Reject buttons AND the "Review change" Modal
>   both approve `via slack` (Paulos=U0BG6ELKMH8 approver) → execute → real PR. `review_slackops_job`
>   Message Shortcut registered + working. `make check` **563 passed**. EC2 stopped ($0).
>   ★ PRESENTATION READY (2026-07-17): 15-slide `docs/presentation/SlackOps DevOps Agent V2.pptx`,
>   OWASP risk→implementation→proof slide, current architecture, speaker script/prompt, and Builder V2 article draft
>   with real Slack/dashboard evidence are in-repo. Public V1 article was updated to current security claims.
>   NEXT: capture the remaining security-denial proof image, rehearse the live demo, and decide whether to publish V2 separately.
>   Guides: `docs/guide/kr/SLACK_NEW_GUIDE.md`, `docs/V2_INTRO.md`/`V2_TEST.md`.
> 1-minute compact entry point (≤60 lines). Standards in harness/CORE_MANDATES.md; work authority is NEXT_PLAN.md > docs/plans/.

## Read Path (session start/resume)
harness/CONTEXT_BRIDGE.md → docs/AGENT_BRIEF.md → docs/STATUS.md → docs/NEXT_PLAN.md
→ (if needed) top of docs/PROGRESS_LOG.md → (if needed) docs/archive/

## Snapshot
- **What:** Slack natural-language command → Claude Code Headless on EC2 analyzes AWS/K8s/Terraform/GitHub context → ops automation.
  MVP = Read-Only analysis + PR creation.
- **Differentiator:** Not just a bot but a reference for "how to run an agent safely" — security (permissions + injection defense) + observability (OTel).
- **Behavior:** command routing + job queue + permission gate + sanitizer + claude_runner + allowlist
  (`run_for_command` single entry) + command_guard (PreToolUse argv schema = the execution boundary) + logs/diagnose/
  detect (fixed read adapters → isolate → assemble) + store/ (H0 single-table Job/Audit/Telemetry, Sqlite+DynamoDb)
  + telemetry + worker (claim→run→output-gate/complete, audit trajectory + capability drift gate) + tf-review
  (plan-isolated, no apply path) + pr (2-stage gate; execute gets a per-approval scoped write grant).
  **web/ dashboard (Next.js)** = jobs feed / detail (diff gate + Approve/Reject) / metrics; DynamoDB Local docker
  (8930) e2e verified; DDB_ENDPOINT toggles real DynamoDB (Vercel) (D7). Inference = subscription OAuth (D6).
  + **agent autonomous proposal (D9)** — mcp_server (propose_job) + agent_monitor; agent proposes → human approval via
  the existing output gate. JobSource.AGENT + Job.rationale. Runbook docs/runbooks/agent-mcp-demo.md.
  + **conversational producer (D10)** — natural-language chat over a DynamoDB conversation bus + chat_agent poller +
  web Chat. Agent inbound = 0 (poll-only) → works on Vercel. Real Claude e2e verified.
- **Verification:** 3-layer gate — `make check` (563 passed) + ruff + mypy (strict) + documentation budget.
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
