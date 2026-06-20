# DECISIONS — slackops-devops-agent
Last updated: 2026-06-17

> Hard-to-reverse decisions only. Format: Decision / Reason / Impact. Updated via /checkpoint.

## D1 — Slack connection is Socket Mode only
- Decision: use Bolt Socket Mode only, with no inbound HTTP endpoint / public HTTPS / ALB / certificate.
- Reason: smaller attack surface + simpler infra. No inbound port needed.
- Impact: public webhook-based features impossible. Runs on EC2 outbound only.

## D2 — Job queue is SQLite (MVP only)
- Decision: MVP job queue is SQLite. Never call/use it as a prod datastore.
- Reason: MVP simplicity. Operational-scale datastore is out of scope.
- Impact: must replace when scaling. Do not use the term "prod store" in docs.

## D3 — Credentials via IAM Instance Profile only
- Decision: never store/commit an Access Key. EC2 Instance Profile only.
- Reason: least privilege + prevent key leakage (the differentiating security axis).
- Impact: local/CI runs need a separate credential path. Commit only the example .env.

## D4 — Package/project name = slackops-devops-agent
- Decision: pyproject `name` and identifiers are `slackops-devops-agent` (reflecting the SlackOps folder name).
- Reason: aligns with the current work folder name. Adopted instead of the BOOTSTRAP-suggested slack-devops-agent.
- Impact: consistent code/config identifiers. Doc body also uses this name.

## D5 — H0 hackathon pivot: DynamoDB dual control plane (Vercel + Slack), B2B track
- Decision: for the H0 hackathon submission (deadline 2026-06-30), expand to "One Agent, Two Control Planes".
  Promote the job queue from SQLite → a **DynamoDB single table** (jobs·audit·telemetry), and unify an office-facing **Vercel/Next.js
  dashboard** (server actions↔DynamoDB) + a remote-facing Slack onto the same DynamoDB queue. Move commands from synchronous calls
  to an **async job model**. Submit to Track 2 (B2B).
- Reason: meet the hackathon pass gate (Vercel frontend + AWS DB + full stack) while reusing the existing backend (permissions·injection-defense·
  claude_runner·allowlist·telemetry). Shared state across the two interfaces is impossible with a single-writer SQLite →
  DynamoDB is a design necessity. One build covers hackathon + AWSKRUG talk + PACE + article.
- Impact: SQLite is demoted to a local-test implementation (behind the JobStore protocol). The no-inbound invariant stays on the Slack path,
  while Vercel is a separate outbound AWS SDK surface. New dependencies boto3 (runtime) / moto (test). Plan: docs/plans/
  2026-06-12-h0-hackathon.md, branch hackathon-h0.

## D6 — Claude inference via subscription-account OAuth token (not Bedrock/API Key)
- Decision: run EC2's Claude Code Headless inference with a **subscription-account long-lived token** (`claude setup-token` →
  `CLAUDE_CODE_OAUTH_TOKEN`, SSM SecureString `/slackops/CLAUDE_CODE_OAUTH_TOKEN`).
  Do not put `ANTHROPIC_API_KEY` on EC2 (block the API-billing path). No Bedrock.
- Reason: preserve the $63.91 AWS credit for infra only (EC2/DynamoDB) — attribute inference cost to the subscription account to
  keep them separate. (The H0 credit request was rejected — proceed via the free/subscription path.)
- Impact: user-data.sh loads the OAuth token from SSM. On token expiry: reissue → refresh SSM → restart the service.
  Recommended to confirm the subscription terms for server-automation use of a personal subscription token.

## D7 — web/ dashboard: local uses DynamoDB Local (offline), deploy uses real DynamoDB (DDB_ENDPOINT toggle)
- Decision: switch the dashboard data source via the `DDB_ENDPOINT` env — when set, DynamoDB Local (local,
  dummy keys); when unset, real DynamoDB (Vercel/EC2, AWS SDK default credential chain). The approval action does a direct
  UpdateItem (ConditionExpression) + audit append to DynamoDB in the server action — mirroring the Python store contract.
- Reason: run local dev/demo without real AWS credentials (offline) for security/convenience, while the same code switches to a
  real Vercel deploy (env-only change). Works on Vercel + DynamoDB alone even after EC2 is stopped during judging.
- Impact: web/ is a separate Python-independent surface (the single source of truth for the schema is src/app/store/, TS only mirrors it).
  Real DynamoDB reads need a least-privilege IAM key (USER_GUIDE.md §5). Port 8930 default.

## D8 — overnight harness: converge on the in-house plugin (overnight-harness) as the single source
- Decision: retire the repo's home-grown harness (`.claude/skills/*`, `bin/overnight/*`, `docs/LOOP_ENGINEERING.md`)
  and make the **overnight-harness plugin the single source**. Runner = `scripts/overnight/`, repo specifics =
  `.claude/harness-config.json` (gate = `make check`, docs.*, budgets, archive_dir = docs/archive), bible↔repo
  mapping = `docs/engineering/interp/INTERPRETATION.md`. Preserved: `harness/{CORE_MANDATES,CONTEXT_BRIDGE}`,
  docs status files, interactive `.claude/settings.json`.
- Reason: remove the cost/confusion of maintaining two copies of the same concept + enable reuse in other repos. The plugin skills
  can absorb paths/gate via harness-config, making convergence clean (skill code in the plugin, content in the repo).
- Impact: skill invocations are provided by the plugin (`/sync` etc.). Runner path bin→scripts, gate unified to `make check`,
  archive docs/archive. The unattended permission boundary is `scripts/overnight/overnight-settings.json` (--settings isolation).

## D9 — agent autonomous proposals: expose the Job Queue as an MCP server (shared producer for human/agent)
- Decision: extend the control plane from humans (slack/web) to **agents (MCP)**. `src/app/mcp_server.py`
  exposes `propose_job`/`list_pending` (FastMCP, server=`slackops`) → an ops agent proposes to the queue.
  **Reuse the existing output gate** (no new store state): proposal = PENDING/source=agent, an L1 write halts in
  the worker's await_approval to awaiting_approval → human approval. Add a dedicated `JobSource.AGENT` +
  `Job.rationale` field (extra is not persisted in the store, so a dedicated field is required). The demo defaults to a Tier1
  simulator (rule-based, no token needed); Tier2 real `claude -p --mcp-config` is optional (token required).
- Reason: an implementation of the project thesis ("operate agents safely") — agents are free to do L0 observe, but L1
  and above are proposals only with disposition by a human. MCP is the standard for "exposing tools to an agent", so it fits propose_job.
  Keeps default-deny (permissions registry) blocking direct free-text wiring (injection defense).
- Impact: `mcp>=1.0` core dependency (lazy import). claude_runner.build_command(mcp_config) added.
  web shows an agent badge + rationale. dynamodb-local exposes host 8931 (host monitor access).
  The local demo has no worker running, so proposals stay pending (a full run needs claude+worker). Runbook
  `docs/runbooks/agent-mcp-demo.md`.

## D10 — conversational producer: DynamoDB as an async message bus between web↔agent (streaming ≠ inbound)
- Decision: replace the Job Queue's selectbox producer with **natural-language chat**. Implement "streaming chat with Claude
  in the browser" **with no inbound port** — web writes the user turn to DynamoDB (`CHAT#`), and
  `chat_agent` polls (outbound-only), runs Claude with `--output-format stream-json`, appends response chunks
  to DynamoDB, and web polls every ~800ms to render Markdown. When Claude calls `propose_job`, the existing output
  gate applies (approve/reject). The chat schema **overloads the existing GSI1 as `CHATSTATUS#`** (no new GSI 0).
- Reason: the alternatives — (a) local claude-in-web is impossible on a Vercel deploy, (b) an agent inbound `/chat`
  endpoint conflicts with the "Socket Mode / 0 inbound" security differentiator (a judging point). The DynamoDB bus **works on Vercel
  + keeps 0 inbound** and strengthens the "DynamoDB = async bus for two control planes" story (DB axis).
  User input is sanitizer-isolated + propose_job (read-only) only → preserves injection defense / template mandate.
- Impact: store/chat_store.py (ChatStore) + claude_runner.run_headless_stream + chat_agent.py (polling
  consumer) + web Chat.tsx/chat-actions/api·route. Streaming fidelity is v1 polling (~800ms chunks, not per-token
  — real SSE can follow via a Vercel bridge). In ops (EC2), chat-agent runs as a resident systemd service. On page reload,
  chat state resets (convId not persisted). Design: docs/plans/2026-06-19-web-chat-producer.md.

## D11 — agent-only docs in English + doc-budget gate (per-session token cost)
- Decision: write agent-only/operational docs in **English** (entry docs AGENT_BRIEF/STATUS/NEXT_PLAN/PROGRESS_LOG,
  CLAUDE.md, harness/*, docs/engineering bibles + interp, DOCS_POLICY/COMPLETED_SUMMARY/DECISIONS, scripts/overnight/PROMPT.md).
  User-facing/human-run docs stay Korean (USER_GUIDE, QA_LIST, action_item, docs/runbooks/*, README). Add a deterministic
  `harness/check-doc-budget.sh` enforcing entry-doc line caps (60/120/120/120) wired into `make check`.
- Reason: those docs load on **every** session/overnight iteration; Korean prose costs ~1.5–2× tokens/char vs English
  (port doc measured -16.4% on the fixed-cost set). The gate hard-stops entry-doc bloat. Markers/identifiers stay verbatim
  ([auto]/[manual]/[blocked], status boxes, paths, make targets) — runner greps + skill triggers unaffected.
- Impact: ~13 docs translated in place (filenames/links/structure unchanged). `make check` now includes `check-doc-budget`.
  User replies remain Korean. Source: docs/archive/token-optimization-port.md.

## D12 — code navigation is LSP-first; Quarkify index retired
- Decision: use Claude Code LSP (pyright) as the navigation tool (workspaceSymbol / findReferences / incoming·outgoingCalls);
  reserve grep for string literals, non-Python files, whole-tree text. **Retire Quarkify** entirely — delete the `.quarkify/`
  artifact, `tools/quarkify/`, `harness/check-quarkify.sh`, the three Makefile targets, the `.gitignore` entry, and the
  CLAUDE.md `## Quarkify` / CORE_MANDATES §7 guidance (replaced with LSP-first).
- Reason: measured 2026-06-19 on this repo — LSP strictly dominates Quarkify on definition (line+kind direct vs empty-folder
  re-read tax), call graph (caller fn + exact `line:col` vs structural path only), and references (type-aware 13 vs grep
  substring 36). Quarkify's one edge (broad symbol search) is also beaten by `workspaceSymbol` (line+scope). Net removal of
  ~340 lines + per-session entry-doc tokens, no capability lost.
- Impact: no `make quarkify*` targets; navigation guidance lives in CLAUDE.md "## Code navigation (LSP)". History preserved in
  docs/archive/quarkify-port.md and PROGRESS_LOG (the port still happened — only the tool is retired).

## D13 — diagnose/logs CloudWatch access is agentic via AWS API MCP (not boto3 pre-fetch)
- Decision: `/devops diagnose` and `/devops logs` no longer pre-fetch CloudWatch via boto3. The Claude Code subprocess calls the
  **awslabs AWS API MCP server** (`uvx awslabs.aws-api-mcp-server@1.3.45`, tools `call_aws`/`suggest_aws_commands`) itself,
  with **`READ_OPERATIONS_ONLY=true`** forced. New `src/app/mcp_config.py:aws_mcp_config_json()`; `run_for_command` threads
  `mcp_config` → `run_headless`; allowlist `logs`/`diagnose` swapped `Bash(aws logs:*)` → `mcp__awsapi__*`. boto3
  `fetch_cloudwatch_logs` kept as a fallback (handlers run agentic on `fetcher=None`, legacy pre-fetch on injected fetcher).
  kubectl/git stay pre-fetched + `<untrusted_data>`-isolated.
- Reason: AWS MCP is purpose-built for agents; the security boundary is the read-only IAM role + server read-only mode + strict
  allowlist, not boto3 vs MCP. Aligns with the project already using MCP for the propose_job control plane (D9). Verified locally
  (real CloudWatch via MCP; write `create-log-group` → "denied by security policy").
- Impact: **prompt-injection model shifts** — CloudWatch tool_result enters Claude's context directly, bypassing the
  `<untrusted_data>` isolation that pre-fetched logs had. Accepted trade-off; the hard boundary is now IAM read-only +
  `READ_OPERATIONS_ONLY` + `--strict-mcp-config` + read-only-tool allowlist (documented in the module docstrings). EC2 needs
  `uv`/`uvx` (user-data installs + pre-warms). Submission narrative wording: "least-privilege at the IAM + tool-allowlist boundary".
