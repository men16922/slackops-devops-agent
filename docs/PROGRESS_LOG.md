# PROGRESS_LOG — slackops-devops-agent
Last updated: 2026-06-19

> Latest 3–5 increments (≤120 lines, newest on top). When it overflows, split into docs/archive/progress-YYYY-MM.md. Append via /checkpoint.
> Original 2026-06-11~12 first-half entries: docs/archive/progress-2026-06.md

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

## 2026-06-18 — session bundle: Quarkify port + worker local entry + web Markdown/sorting + GUIDE merge/QA
- Status: Done. H0 local demo quality/verification cleanup (separate [manual] AWS track unchanged).
- Changed: Quarkify code-topology index port (tools/quarkify + non-blocking freshness + policy doc, measured anchor).
  worker local CLI entry (`python -m app.worker`, stores_from_env) → full loop locally complete. Makefile
  DEV_ENV (PYTHONPATH=src + DDB dummy keys) — agent-monitor/worker/chat-agent. web result Markdown
  render (Markdown.tsx, nested emphasis) + agent source sorting. END_USER_GUIDE→USER_GUIDE merge, QA_LIST.md created.
- Verified: `make check` green (via 250→262 passed) + Playwright covering all §3-A dashboard click UX (approval transition/
  optimistic lock/Telemetry/producer) + real Claude diagnose full loop ($0.25/4838tok). Evidence docs/images/.
- Blockers: None.
- Next: conversational producer (2026-06-19 above) → H0 [manual] submission track.

## 2026-06-17 — agent autonomous proposal loop (MCP propose_job) + human web producer (DECISIONS D9)
- Status: Done. Extended the control plane to agents — "detect→propose→human approve" loop implemented (local e2e).
- Changed: **src/app/mcp_server.py** (new) propose_job/list_pending (FastMCP, server=slackops, pure
  logic/SDK wrapper split, permissions default-deny reuse). **src/app/agent_monitor.py** (new) Tier1
  simulator (rule-based detect, no token needed) + Tier2 real run_monitor_headless (--mcp-config). store/
  (base/dynamodb/sqlite) gained `JobSource.AGENT` + `Job.rationale` dedicated fields (required since extra isn't persisted).
  claude_runner.build_command (mcp_config)→--mcp-config + --strict-mcp-config. **web/**: human producer
  (NewCommand chat/selectbox + actions.enqueueJob) + agent badge/rationale callout, 2 seed agent
  samples, docker-compose dynamodb-local 8931 exposed. pyproject mcp>=1.0 (+mypy override). Makefile
  mcp-server/agent-monitor. END_USER_GUIDE.md, docs/runbooks/agent-mcp-demo.md. Commit f1caa80.
- Verified: `make check` green (**249 passed, 1 skipped** · ruff · mypy strict) + web `tsc` green +
  docker e2e (28 seeds, home/detail agent render — 🤖 badge/rationale/diff/Approve) + Tier1 live
  (agent_monitor simulator→DynamoDB Local 8931→FEED 3 agent proposals confirmed).
- Blockers: None. (Tier2 real claude -p needs OAuth token → env unset, runbook documented but not run.)
- Next: H0 [manual] — DynamoDB provision/Vercel deploy/submission. (local demo: worker not running → proposals stay pending.)

## 2026-06-17 — overnight-harness plugin convergence (remove repo-local harness duplication)
- Status: Done. Made the homemade plugin the single source — removed 3-layer duplication of skills/runner/engineering docs (DECISIONS D8).
- Changed: harness-init scaffold (scripts/overnight/* + docs/engineering/* bibles + .claude/harness-config.json
  + docs/test/bible + Makefile snippet). Deleted 4 repo-local skills (.claude/skills/{sync,checkpoint,tidy-docs,
  overnight-report}) → use plugin. Moved runner bin/overnight → scripts/overnight (PROMPT ports repo invariants
  CORE_MANDATES/aws→mock/lazy import/CONTEXT_BRIDGE read path/Korean, overnight-settings reinforced with aws deny).
  docs/LOOP_ENGINEERING.md → absorbed into docs/engineering/interp/INTERPRETATION.md then deleted. New Makefile
  (check=pytest+ruff+mypy + overnight targets). Archive bin/docs/archive → moved to docs/archive.
  Updated CLAUDE.md/DOCS_POLICY/README/.gitignore references. (Preserved: harness/ mandates, docs status docs, interactive settings.)
- Verified: `make check` green (229 passed, 1 skipped · ruff · mypy). Structure verified (0 duplicate skills, bin removed,
  0 bin references in active docs, run.sh/status.sh syntax OK). Live overnight-once smoke to proceed after commit.
- Blockers: None. (Skill bare invocation name `/sync` resolution to be confirmed in real use.)
- Next: H0 [manual] — DynamoDB provision/Vercel deploy/submission.

## 2026-06-16 — web/ dashboard (Next.js, local Docker) + USER_GUIDE.md + Claude subscription inference decision
- Status: Done. First front-end implementation of the H0 core stack (Vercel front + DynamoDB) — through local e2e.
- Changed: **web/** new — Next.js 14.2.35 App Router (TS). lib/{types,time,ddb,format}.ts
  (single-table contract TS mirror — GSI2 FEED/AUDIT/METRIC queries, isomorphic with _util.py utcnow_iso/day_of),
  app/{page(jobs feed),jobs/[id](detail + diff output gate + Approve/Reject + audit),metrics},
  actions.ts (approval server action = _conditional_set ConditionExpression + audit append mirror),
  scripts/seed.mjs (create table from create-table.sh schema + 22 mocks). docker-compose (dynamodb-local
  offline + seed + web, **port 8930**, dummy keys — no real AWS needed), Dockerfile, .env.local.example.
  **USER_GUIDE.md** (root) — secret manual-entry guide (Slack/Claude→SSM, AWS keys only via least-privilege IAM
  when reading Vercel/real DynamoDB, issuance/policy/rotation/judging-period cost saving). deploy/{ec2/user-data.sh,README.md}
  add CLAUDE_CODE_OAUTH_TOKEN (SSM) load. .gitignore web/ entry.
- Verified: `next build` green (TS strict) + **docker compose up e2e**: 22 seeds, web 8930 responds,
  jobs/detail/metrics render + **approval transition works / duplicate-approval ConditionalCheckFailed rejection** (optimistic lock) confirmed.
  3-layer gate: pytest 229 passed/1 skipped · ruff green · mypy green (src unchanged).
- Blockers: None. (remaining postcss moderate/high vuln needs Next 16 major — deferred.)
- Next: [manual] — DynamoDB provision → EC2 e2e capture → Vercel deploy (real DynamoDB, read-key env) → submission.
