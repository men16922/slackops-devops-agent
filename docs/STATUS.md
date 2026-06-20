# STATUS — slackops-devops-agent
Last updated: 2026-06-20

> Current state/verification/risks (≤120 lines). Source of truth. Update via /checkpoint.

## Current summary
- Day 1–3 **local implementation complete**: Socket Mode routing + `/devops ping` + job queue + permission gate
  + FastAPI health/metrics. deploy/ artifacts (IAM/EC2/EventBridge/ADOT) ready-to-run.
- AWS/Slack **cloud deploy A–C verified once** (2026-06-20): Slack App + SSM tokens + IAM + DynamoDB(us-east-1) + EC2 →
  `/devops ping` pong from `ip-…ec2.internal`. EC2 then terminated (cost ~$0). Runbook docs/runbooks/deploy-checklist.md.

## Verification Baseline
- 3-layer gate: `python3 -m pytest tests/ -q` → **307 passed, 1 skipped** (fastapi-not-installed local-only skip)
  + `ruff check src tests` + `mypy src` (strict) all green.
- diagnose/logs **agentic AWS API MCP** (D13) e2e: local (`handle_logs`/`handle_diagnose('checkout-service')` via real claude +
  `uvx awslabs.aws-api-mcp-server@1.3.45`) AND **cloud via Slack on real EC2 using Instance Profile (zero stored keys)** — real
  CloudWatch (streams/trace-ids quoted); write op → "denied by security policy". EC2 terminated after.
- **All user-facing text English** (H0): agent Slack/chat responses + web/ dashboard UI. Playwright verified English render (no Korean DOM).
- web/: `next build` green (TS strict) + `docker compose up` e2e — 22 seeds, 8930 responds, jobs/detail/metrics
  render + approval transition / duplicate-approval ConditionalCheckFailed rejection confirmed (2026-06-16).
- lazy-import design — all modules import-safe even without fastapi/slack_bolt installed.
- code-review (high) follow-up: 10 findings fixed — route exception safety net, sanitizer unclosed tag,
  kubectl flag injection, CloudWatch latest events, run.sh limit decision, command registry unification, etc.
- `/devops ping` cloud e2e **verified** (2026-06-20, real EC2→Slack). MCP-path diagnose/logs verified locally; cloud redeploy pending.

## What works
- command routing (default deny + forbidden-invariant rejection), ping handler, SQLite job queue (atomic claim),
  permission engine (L0/1 active, L2 disabled), health/metrics (127.0.0.1 only),
  sanitizer (wrap_untrusted neutralizes forged tags + build_prompt template enforcement),
  claude_runner (run_headless — runner injection, allowedTools passthrough, JSON→RunResult parsing, timeout),
  allowlist (per-command Tool Allowlist mapping + run_for_command single entry point — permissions gate →
  allowlist → run_headless, forbidden keywords validated at import-time, default deny),
  commands/logs (handle_logs — fetcher inject→sanitizer isolate→run_for_command assemble,
  service-arg regex validation, boto3 lazy default fetcher),
  commands/diagnose (handle_diagnose — multi-source fetchers injected (logs/kubectl/git diff),
  per-source failure isolation, single isolation block per section marker, no Claude call when all sources empty),
  routing registration (register_default_commands — ping/logs/diagnose, module attribute lookup at call time),
  store/ (H0 single-table — JobStore state machine + claim atomicity, AuditStore append/job/day feed,
  TelemetryStore record/feed — each with Sqlite+DynamoDb implementations, moto equivalence verified),
  telemetry (record_run_metrics — writes to injected TelemetryStore, setup_telemetry is OTel lazy stub),
  worker (Worker.process_one — claim→executor→await_approval output gate if diff unapproved,
  else DONE / FAILED on exception + audit/metric write-back, run_forever injected-sleep polling,
  default_executors ping/logs/diagnose/tf-review/pr, commands outside mapping default deny),
  commands/tf_review (handle_tf_review — PlanFetcher injected (default argv fixed to `terraform plan`,
  no-apply-path test), plan isolation → risk/cost/security review),
  commands/pr (handle_pr 2-stage — prepare removes push/PR tools from argv (exclude_tools,
  narrowing-only) and extracts diff via marker → PrResult.diff → worker gate, execute (post-approval) only
  uses full allowlist for push + `gh pr create`; description passed only as isolation block after length validation),
  tf-review registered on the slack synchronous path (pr is worker-only since its gate requires store state).
- telemetry (setup_telemetry real implementation — TracerProvider+SimpleSpanProcessor, exporter inject/OTLP lazy,
  None when not installed; record_run_metrics emits devops.run span when tracer injected, store record invariant),
  instrumentation coupling (run_for_command on_metrics — single entry point instruments all Claude calls, 4 handlers
  passthrough, worker writes back real tokens/cost to CommandOutcome/metric/job,
  Worker emits OTel span when tracer injected). No stubs remaining.
- **web/ dashboard (Next.js 14.2.35 App Router, TS)** — local e2e verified. lib/ddb (single-table contract
  TS mirror: GSI2 FEED/AUDIT/METRIC queries), app/{jobs feed, detail = diff output gate + Approve/Reject + audit,
  metrics aggregation}, actions (approval server action = ConditionExpression transition + audit append, optimistic lock),
  scripts/seed.mjs (create-table.sh schema + 22 mocks). docker-compose (dynamodb-local offline + seed + web,
  port 8930, dummy keys = no real AWS needed). DDB_ENDPOINT toggle switches local↔real DynamoDB (D7).
- ops deploy prep: user-data.sh/deploy README load Claude subscription OAuth token (SSM) added (D6).
  SLACK_GUIDE.md / DASHBOARD_GUIDE.md (root) — operator secret + deploy + dashboard guides.
- **agent autonomous proposal loop (D9)** — extends the control plane to a shared human+agent producer.
  mcp_server (propose_job/list_pending — FastMCP server=slackops, pure-logic/wrapper split, permissions
  default-deny reuse), agent_monitor (Tier1 simulator detect rules + Tier2 real claude -p
  --mcp-config), claude_runner.build_command (mcp_config). Reuses the existing output gate (no new store state):
  proposal = PENDING/source=agent, L1 awaits human approval via await_approval. store adds JobSource.AGENT
  + Job.rationale. web/ has a human producer (NewCommand chat/selectbox + enqueueJob) + agent badge/
  rationale display, 2 seed agent samples, dynamodb-local 8931 exposed. Runbook docs/runbooks/agent-mcp-demo.md.

- **conversational producer (D10, 2026-06-19)** — replaces selectbox with natural-language chat. DynamoDB conversation bus
  (store/chat_store.py, GSI1 overloading) + claude_runner.run_headless_stream (stream-json) + chat_agent.py
  (polling consumer, sanitizer isolation, propose_job only) + web Chat.tsx (polling Markdown render) + api/chat route.
  Agent inbound = 0 (poll-only) → works on Vercel. **Real Claude e2e verified** (checkout 504 diagnosis + propose_job load).
  make chat-agent. (web result Markdown render + Quarkify port + worker local entry also in this session.)

- **demo/quality cleanup (2026-06-19 round 2)**: `make demo` (scripts/demo.sh) runs the full local stack in one shot (web+DB+chat_agent+worker).
  Conversational-producer orphan convId lock fix (self-heal after reseed + retry). Chat/result pretty render
  (Markdown tables/horizontal-rules/links + claude_runner ANSI strip). user-data.sh now keeps worker/chat_agent systemd resident
  (closes the cloud full-loop gap). Playwright real-Claude e2e verified chat behavior + table render.

- **safe-autonomy loop + governance Detections (F1–F5, 2026-06-20)** — monitor resident (systemd `--loop`,
  dedupe guard) + Slack proposal notify (`proposal_notifier` thread in main) + dashboard 🔔 bell
  (`/api/jobs/agent-pending`) + governance `detect` scan-as-job (agentic AWS MCP read-only; iam/config/ssm/incident,
  L0) + Detections menu (`/detections` ON/OFF + Scan now, toggles in `CONFIG#detections`). All gated (307 passed,
  next build green). Real scan findings = cloud-only (EC2+IAM). Reframe: triage/safe-response layer over existing signals.

## Active Focus
- F1–F5 local-complete + gated. **Next: local make-demo e2e walk-through**, then H0 [manual] submission —
  Vercel deploy (link/Team ID) + EC2 1-run **cloud captures** (real CloudWatch diagnose / scan findings / write-denied) →
  artifacts (architecture diagram / DynamoDB screenshot / 3-min English demo / text — drafts in docs/guide/{en,kr}/DEVPOST·DEMO_SCRIPT). Deadline 2026-06-29.
- AWS credit request **rejected** → $63.91 on hand + free tier (live: DynamoDB `slackops-agent` us-east-1, IAM role/profile, SSM tokens).

## Open Risks
- untrusted input (git diff / kubectl) isolated in `<untrusted_data>`; **CloudWatch now enters via AWS MCP tool_result (D13) —
  bypasses that isolation**. Boundary = IAM read-only + `READ_OPERATIONS_ONLY` + `--strict-mcp-config` + read-only-tool allowlist.
- Never use credentials other than IAM Instance Profile (.env commits example only).
- EC2 always-on cost — verify EventBridge schedule stop/start.
- Non-goals (out of scope): public HTTPS endpoint, EC2 always-on, Level 2 (Execute), Production/deploy/IAM/DB changes,
  calling SQLite a prod datastore.
