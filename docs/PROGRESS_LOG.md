# PROGRESS_LOG — slackops-devops-agent
Last updated: 2026-06-20

> Latest 3–5 increments (≤120 lines, newest on top). When it overflows, split into docs/archive/progress-YYYY-MM.md. Append via /checkpoint.
> Original 2026-06-11~12 first-half entries: docs/archive/progress-2026-06.md

## 2026-06-20 — safe-autonomy loop visible + governance Detections menu (F1–F5)
- Status: Done (local-complete + gated). Cloud captures pending (manual).
- Changed: **F1 monitor resident** — dedupe guard in `propose_job_impl` (source=AGENT open-dup skip) +
  4th systemd unit (`agent_monitor --loop 300`). **F2 Slack notify** — new `proposal_notifier.py`
  (pure `notify_new_proposals` + `run_forever`) as a daemon thread in `main.py` (reuses Bolt client;
  `SLACK_NOTIFY_CHANNEL`/`DASHBOARD_URL`). **F3 dashboard bell** — `listPendingAgentJobs` +
  `/api/jobs/agent-pending` + `NotificationBell.tsx` (poll + localStorage watermark). **F4 governance
  detect** — `commands/detect.py` (scan-as-job, agentic AWS MCP read-only; iam/config/ssm/incident) +
  `detect` L0 (permissions/allowlist/worker) + `store/detection_config.py` (Sqlite+DynamoDb) +
  `agent_monitor.enqueue_due_scans` scheduler + IAM read perms (access-analyzer/config/ssm).
  **F5 Detections menu** — `web/lib/detections` catalog + `getDetectionConfigs` +
  `setDetectionEnabled`/`scanNow` + `/detections` page + `DetectionCard` + nav + seed + css.
  Docs: `features.md` updated; new `DEVPOST.md`/`DEMO_SCRIPT.md` (en+kr).
- Verified: **`make check` 307 passed · ruff · mypy 31 · doc-budget** + web **`next build`** green
  (`/detections`, `/api/jobs/agent-pending`). make-demo e2e + cloud captures = pending (manual).
- Blockers: None.
- Next: local make-demo walk-through; Vercel deploy + EC2 1-run cloud captures (real CloudWatch / scan findings / write-denied).

## 2026-06-20 — cloud MCP e2e (Instance Profile) + full English-ification (agent + web UI)
- Status: Done. Verified the AWS MCP path on real EC2, then switched all user-facing text to English for H0 submission.
- Changed: **English-ification** — agent Slack/chat responses (diagnose/logs/tf-review/pr prompt templates + slack_handler /
  _replies / usage hints + chat_agent / agent_monitor / mcp_server propose_job) and **web/ dashboard UI** (page / Chat /
  job-detail Output Gate / metrics / enqueue+chat server-action messages). Tests updated to new English fragments. Commits
  940777f (agent), f7ce90a (web). Code comments left Korean (internal).
- Verified: **cloud e2e** — redeployed EC2 (t3.medium, user-data installs/pre-warms uvx), Slack `/devops diagnose
  checkout-service` → AWS MCP→CloudWatch via **Instance Profile (zero stored keys)** + read-only (write `create-log-group`
  → "denied by security policy"); EC2 then terminated. `make check` 278 passed/ruff/mypy(28)/doc-budget. Local web: docker
  `next build` green + Playwright `/`·job-detail·metrics render English (no Korean in DOM, only source comments).
- Blockers: None.
- Next: H0 [manual] — Vercel deploy (link/Team ID) → submission artifacts (diagram / DynamoDB screenshot / 3-min English demo / text).

## 2026-06-20 — cloud deploy A–C verified + diagnose/logs → agentic AWS API MCP (DECISIONS D13)
- Status: Done. Full cloud deploy proven end-to-end, then migrated CloudWatch access from boto3 to AWS MCP, verified local.
- Changed: **deploy** — single ops runbook `docs/runbooks/deploy-checklist.md`; region default `ap-northeast-2`→`us-east-1`
  (matches code), EC2 `c7i.large`→`t3.medium` (Claude headless = remote inference, bursty I/O), `.claude/settings.json` allows
  `aws`. Region bug fix: botocore reads `AWS_DEFAULT_REGION` not `AWS_REGION` → user-data emits both.
  **migration (D13)** — new `src/app/mcp_config.py` (`aws_mcp_config_json`, AWS API MCP @1.3.45, `READ_OPERATIONS_ONLY=true`);
  `run_for_command` threads `mcp_config`; allowlist logs/diagnose → `mcp__awsapi__*`; handlers dual-mode (agentic on
  `fetcher=None`, legacy pre-fetch on injected); boto3 `fetch_cloudwatch_logs` kept as fallback; user-data installs/pre-warms
  `uv`/`uvx`. Injection-model shift documented in module docstrings.
- Verified: full A→C cloud e2e on real EC2 (`/devops ping` → pong from `ip-172-31-…ec2.internal`, SSM-driven). After migration:
  **`make check` 278 passed · ruff · mypy 28 · doc-budget**. Local real e2e — `handle_logs`/`handle_diagnose('checkout-service')`
  via real claude+AWS MCP (real CloudWatch streams/trace-ids quoted). Read-only proof: write `create-log-group` →
  "denied by security policy". EC2 then **terminated** (cost ~$0).
- Blockers: None.
- Next: Phase 3-deploy — relaunch EC2 (t3.medium, user-data installs uvx) + Slack cloud e2e of MCP path. Then H0 [manual] Vercel/submission.

## 2026-06-19 — Quarkify retired → LSP-first code navigation
- Status: Done. Measured LSP vs Quarkify on this repo; Quarkify removed (decision D12).
- Changed: navigation guidance is now LSP-first. CLAUDE.md `## Quarkify` → `## Code navigation (LSP)`;
  CORE_MANDATES §7 rewritten (workspaceSymbol/findReferences/incoming·outgoingCalls; grep for literals/non-py/text).
  Removed Makefile targets (quarkify/-setup/-check) + .PHONY, harness/check-quarkify.sh, tools/quarkify/*, .quarkify/,
  .gitignore entry. DECISIONS D12 added. History (archive/quarkify-port.md, STATUS/AGENT_BRIEF mentions) preserved.
- Verified: measured 3 tasks same symbols — def: LSP `base.py:91`+kind vs Quarkify empty-folder re-read;
  callgraph: `incomingCalls` main@318 callsite 349:47 vs structural path only; refs: `findReferences` 13 type-aware
  vs grep 36 substring. `make check-doc-budget` OK (AGENT_BRIEF 50/60 etc). Full `make check` not re-run this entry.
- Blockers: None.
- Next: H0 [manual] — AWS provision/deploy/submission (unchanged).

## 2026-06-19 — make demo + chat orphan lock fix + pretty rendering + cloud systemd gap
- Status: Done. Demo chat stuck (real bug) diagnosed/fixed + output readability + EC2 full-loop gap.
- Changed: **make demo** (scripts/demo.sh) — docker (web+DB+seed) + chat_agent + worker in one shot, Ctrl-C cleanup.
  **fix(web) orphan convId lock**: old convId in localStorage + in-memory DDB reseed lost the conversation META →
  failed send condition mistaken for "responding" + "new conversation" button hidden = permanent lock. chat-actions
  now distinguishes gone/busy (GetItem), Chat retries a new conversation on gone + polling self-heals. **pretty render**:
  Markdown.tsx GFM tables/horizontal-rules/links (scheme whitelist) + globals.css styling, claude_runner
  strips ANSI (CSI) from result/stream chunks (4 tests). **deploy**: added 2 worker/chat_agent
  systemd units to user-data.sh (Restart=always, outbound polling → inbound stays 0), README 3-service. QA_LIST updated.
- Verified: `make check` **274 passed, 1 skipped** · ruff · mypy (strict 27). web `next build` green.
  **Playwright real-Claude e2e**: reseed → refresh → self-heal → send → table response render (0 console errors).
  Evidence docs/images/chat-pretty-render-verified.png. bash -n user-data.sh OK.
- Blockers: None.
- Next: H0 [manual] — AWS provision/deploy/submission. (worker auto-runs seed pending jobs via real Claude → watch token spend.)

## 2026-06-19 — conversational producer: web chat → agent streaming → propose_job (DECISIONS D10)
- Status: Done. Replaced the selectbox producer with natural-language chat — verified through real Claude e2e.
- Changed: **store/chat_store.py** (new) conversation bus (Conversation/Message/ChatStatus + Sqlite/DynamoDb,
  single-table PK=CHAT#/META, **GSI1 CHATSTATUS# overloading for claim — 0 new GSI**, chunk list_append).
  **claude_runner.run_headless_stream** (new) stream-json line parsing → on_chunk callback + tokens/cost +
  propose_job job_id extraction. **chat_agent.py** (new) polling consumer (claim→sanitizer isolate→stream→
  finish, allowedTools=propose_job only). **web/**: Chat.tsx (polling Markdown render) + chat-actions.ts +
  api/chat/[conv] route, Markdown.tsx shared move, NewCommand removed. mcp_config_json AWS dummy-key
  passthrough (local real Claude). **reload persistence (convId localStorage + "new conversation" button)**. make chat-agent.
  USER_GUIDE §2.4-2.5/runbook updated. (checkpoint follow-up: tidy-docs split PROGRESS_LOG 193→78 lines to archive.)
- Verified: `make check` green (**270 passed, 1 skipped** · ruff · mypy 27 files) + web `next build` TS strict +
  Playwright e2e (input→DynamoDB→chat_agent (mock+**real Claude**)→polling Markdown render + proposal callout→Job Queue).
  Real Claude: checkout 504 multi-turn diagnosis + propose_job real job load confirmed + conversation restored after reload.
  Evidence docs/images/chat-producer-e2e.png.
- Blockers: None.
- Next: H0 [manual] — AWS provision/deploy/submission. (optional: Vercel SSE bridge = token-level real-time, docs/plans §6.)
