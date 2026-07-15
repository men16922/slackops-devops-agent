# STATUS — slackops-devops-agent
Last updated: 2026-07-16

> Current state/verification/risks (≤120 lines). Source of truth. Update via /checkpoint.

## Current summary
- Day 1–3 **local implementation complete**: Socket Mode routing + `/devops ping` + job queue + permission gate
  + FastAPI health/metrics. deploy/ artifacts (IAM/EC2/EventBridge/ADOT) ready-to-run.
- AWS/Slack **cloud deploy A–C verified once** (2026-06-20): Slack App + SSM tokens + IAM + DynamoDB(us-east-1) + EC2 →
  `/devops ping` pong from `ip-…ec2.internal`. EC2 then terminated (cost ~$0). Runbook docs/runbooks/deploy-checklist.md.
- **D15 secure runtime production deployed (2026-07-15):** GitHub OAuth, immutable plan/approval hash, workspace/tool/postcondition validation, approver allowlist/audit chain, EC2 hardening; Vercel and real GitHub login passed.

## Verification Baseline
- 3-layer gate: `make check` → **540 passed** · `ruff` · `mypy src`(strict) · documentation-budget gate all green;
  `cd web && npm run build` and `git diff --check` also pass for D15.
- **Event-driven loop live (2026-06-20, real AWS):** CloudWatch ALARM→EventBridge→Lambda(`alarm_lambda`, detect→propose)→DynamoDB queue→worker(Claude)→DONE→Slack ($0.15/2.7K–6K tok). Serverless producer fires EC2-off; EC2 then terminated → ≈ $0.
- **Vercel dashboard live** on real DynamoDB (link + Team ID captured); `web/lib/ddb.ts` trims env + defaults to us-east-1.
  D15 GitHub OAuth + required allowlist deployed to Production; unauthenticated `/` redirects to `/login`.
- **D16 secure read-adapter hardening (2026-07-15):** logs/diagnose/detect use fixed boto3 evidence adapters + sanitizer isolation; model tool allowlists are empty. Runtime drops generic AWS MCP/uvx, unused S3, broad SSM enumeration, child secrets.
- **D17 role/metadata/egress hardening (real EC2 rehearsal, 2026-07-15):** 1-hour runtime/MCP STS roles, forced rotation, fixed AWS read IAM, four services/timer, IMDS/direct-egress denial, GitHub proxy allow and unlisted-domain deny verified. MCP `ping` audit and deployment fixes verified; instance/artifact removed.
- **P1 central system-boundary audit (real EC2 rehearsal, 2026-07-15):** deployment provisions the 30-day
  `/slackops/security-boundary-audit` group; a root-only audit STS role can create streams/append only, and runtime/MCP cannot
  write it (explicit `PutLogEvents` deny). Fresh EC2 logged `credential_refresh` + URL-free `proxy_denied`; audit env root
  `600`, state root `700`; artifact/instance removed.
- **P2 deterministic scope boundary (real EC2 rehearsal, 2026-07-15):** root-owned env fixes account/region/log-prefix/
  workspace; every command gets a fixed scope before adapter/executor and is rechecked before Claude. Out-of-prefix fetch
  denied before access, Worker emitted `policy_denied` with reason/scope, 24h window verified; artifact/instance removed.
- **P3 managed AWS MCP pilot scaffold (local/CI only, 2026-07-15):** separate-account contract, context-key-constrained Logs
  read policy, CloudTrail violation query. No AWS role, trust policy, endpoint, MCP session, or EC2 rehearsal exists.
- **D19–D23 secure runtime (local/CI, 2026-07-16, commits `3affc65`/`84535bc`+):** all rest on one measurement —
  `--allowedTools 'Bash(echo:*)'` ran `echo hi; whoami` (2.1.210): tool patterns bind a command line's head, not execution.
  **D19** `command_guard` normalizes argv + enforces per-command schemas via a PreToolUse hook (deny beats allowedTools;
  e2e: `;`/`$()` denied, schema match ran). PR write is no longer standing — repo/permission-scoped GitHub App token minted
  only after approval-hash re-verification, then revoked + audited; App unregistered → fails closed.
  **D20** declared 5-class capability taxonomy (old substring classifier scored `git add`/`pytest`/`terraform plan` as
  *no* capability); chain-summed risk vs `RISK_CEILING=10` (write-high/privileged exceed alone → L2/privileged blocked by
  arithmetic); score/ceiling/account/region pinned in the hashed plan; re-approval on read→write escalation/score/account/
  region change; unclassified tool = import error. `pr` risk 6, `tf-review` 1.
  **D21** audit events carry store-assigned step_id/parent_step_id/tool_name/capabilities/target_resource/result_hash and
  form a tree (claim = root; write_credentials_issued descends from its approval step). Trajectory fields hash only when
  set → chains already in DynamoDB still verify. Sqlite↔DynamoDB moto-equivalent; web mirror updated.
  **D22** stream-json for **observation** (`json` output has no tool-call data); dual-shape parser keeps mocks aligned
  with production; each observed call = a `tool_call` step; `resolve_tool` maps observed argv → declared capability via the
  guard's own parse. Real e2e: `claimed → tool_call ×2 → done caps=read` vs static read,write-low.
  **D23** observed capability is a gate, not a note: anything the guard does not authorize, or capability/risk beyond the
  approval, fails the job with a `capability_drift` event (reason kept); failure paths still record what ran. Silent on
  the normal path by design — it speaks only if the guard is bypassed. Verified: authorized=DONE, `curl` observed=FAILED.
- **All user-facing text English** (H0): agent Slack/chat + dashboard UI are English; seed rationales translated (2026-07-15).
- web/: `next build` green (TS strict) + `docker compose up` e2e — 22 seeds, 8930 responds, jobs/detail/metrics render
  + approval transition / duplicate-approval ConditionalCheckFailed rejection confirmed (2026-06-16).
- lazy-import design — all modules import-safe even without fastapi/slack_bolt installed.
- `/devops ping` cloud e2e **verified** (2026-06-20, real EC2→Slack). MCP-path diagnose/logs verified locally; cloud redeploy pending.

## What works
- command routing (default deny + forbidden-invariant rejection), ping handler, SQLite job queue (atomic claim),
  permission engine (L0/1 active, L2 disabled), health/metrics (127.0.0.1 only),
  sanitizer (wrap_untrusted neutralizes forged tags + build_prompt template enforcement),
  claude_runner (run_headless — runner injection, allowedTools passthrough, stream-json→RunResult+ToolCall, timeout),
  allowlist (per-command Tool Allowlist mapping + run_for_command single entry point — permissions gate →
  allowlist → run_headless, forbidden keywords validated at import-time, default deny),
  commands/logs (fetcher inject→sanitizer isolate→run_for_command assemble, service-arg regex, boto3 lazy fetcher),
  commands/diagnose (multi-source fetchers injected (logs/kubectl/git diff), per-source failure isolation, one
  isolation block per section marker, no Claude call when all sources empty),
  routing registration (register_default_commands — module attribute lookup at call time),
  store/ (H0 single-table — JobStore state machine + claim atomicity, AuditStore append/job/day feed,
  TelemetryStore record/feed — each with Sqlite+DynamoDb implementations, moto equivalence verified),
  worker (Worker.process_one — claim→executor→await_approval output gate if diff unapproved, else DONE / FAILED on
  exception + audit/metric write-back, run_forever injected-sleep polling, commands outside mapping default deny),
  commands/tf_review (PlanFetcher injected, argv fixed to `terraform plan`, no-apply path; plan isolation → review),
  commands/pr (2-stage — prepare strips push/PR tools from argv + extracts diff via marker → worker gate; execute
  (post-approval) regains push + `gh pr create` and a scoped write grant; description only as isolation block),
  tf-review is on the slack synchronous path (pr is worker-only since its gate requires store state).
- telemetry (setup_telemetry — TracerProvider+SimpleSpanProcessor, exporter inject/OTLP lazy, None when not installed;
  record_run_metrics emits devops.run span when tracer injected), instrumentation coupling (run_for_command on_metrics —
  single entry point instruments all Claude calls; worker writes back real tokens/cost). No stubs remaining.
- **web/ dashboard (Next.js 14.2.35 App Router, TS)** — local e2e verified. lib/ddb (single-table TS mirror: GSI2
  FEED/AUDIT/METRIC queries), app/{jobs feed, detail = diff output gate + Approve/Reject + audit, metrics aggregation},
  actions (approval server action = ConditionExpression transition + audit append, optimistic lock), scripts/seed.mjs
  (22 mocks). docker-compose (dynamodb-local + seed + web, port 8930). DDB_ENDPOINT toggles local↔real DynamoDB (D7).
  **UI 리디자인(2026-07-10, `35f4b38`)**: AWS 콘솔/Datadog 감성 라이트 테마(KPI 타일, STATUS↔SOURCE 형태 분리,
  제브라 테이블, Chat=ops 카드, LIVE 칩). `next build` green.
- ops deploy prep: user-data.sh/deploy README load Claude subscription OAuth token (SSM) added (D6).
  SLACK_GUIDE.md / DASHBOARD_GUIDE.md (root) — operator secret + deploy + dashboard guides.
- **agent autonomous proposal loop (D9)** — control plane becomes a shared human+agent producer. mcp_server
  (propose_job/list_pending — FastMCP, permissions default-deny reuse), agent_monitor (Tier1 rules + Tier2 real
  `claude -p --mcp-config`). Reuses the existing output gate (no new store state): proposal = PENDING/source=agent,
  L1 awaits human approval. store adds JobSource.AGENT + Job.rationale. Runbook docs/runbooks/agent-mcp-demo.md.

- **conversational producer (D10, 2026-06-19)** — replaces selectbox with natural-language chat. DynamoDB conversation bus
  (store/chat_store.py, GSI1 overloading) + claude_runner.run_headless_stream (stream-json) + chat_agent.py
  (polling consumer, sanitizer isolation, propose_job only) + web Chat.tsx (polling Markdown render) + api/chat route.
  Agent inbound = 0 (poll-only) → works on Vercel. **Real Claude e2e verified** (checkout 504 diagnosis + propose_job). make chat-agent.

- **demo/quality cleanup (2026-06-19 round 2)**: `make demo` (scripts/demo.sh) runs the full local stack in one shot
  (web+DB+chat_agent+worker). Chat/result Markdown render + ANSI strip; user-data.sh keeps worker/chat_agent systemd
  resident (closes the cloud full-loop gap). Playwright real-Claude e2e verified chat behavior + table render.

- **safe-autonomy loop + governance Detections (F1–F5, 2026-06-20)** — monitor resident (systemd `--loop`,
  dedupe guard) + Slack proposal notify (`proposal_notifier` thread in main) + dashboard 🔔 bell
  (`/api/jobs/agent-pending`) + governance `detect` scan-as-job (fixed AWS read adapters; iam/config/ssm/incident, L0)
  + Detections menu (`/detections` ON/OFF + Scan now, toggles in `CONFIG#detections`). Real scan findings = cloud-only
  (EC2+IAM). Reframe: triage/safe-response layer over existing signals.

## Active Focus
- **v2 = AWSKRUG 발표 데모** (branch `v2`, plan `docs/plans/2026-06-25-awskrug-demo.md`). Slack 해커톤 제출 **폐기**(Devpost §3
  Eligibility 한국 미달). 목표 = "Slack 자연어 → 실 AWS 안전 진단 → 승인게이트 → 포스트모템 Canvas" 라이브 데모(보안+관측성 차별점).
- **D1–D3 + 실 Slack sandbox e2e 완료(2026-07-02)** — DM 폴백(register_dm_messages) 경로로 스트리밍→pr 제안→diff+버튼→
  approved 전이(audit via slack)→**Canvas 자동 생성**→footer/payload 확정. ASSISTANT_POLL_TIMEOUT_S(240s).
  **D4 실 AWS 검증(2026-07-06)**: EC2→CloudWatch 진단+write-denied. Modal diff·Shortcut 은 코드 완료(07-15), Slack App
  등록은 수동 잔여. pr execute(실 push)는 발표 시 EC2 라이브 = D19 write credential 리허설과 같은 회차. ★ NEXT = 슬라이드.
- H0 인프라(DynamoDB/Vercel/Lambda/SSM) 유지, **비용 ≈ $0**. AWS credit rejected → $63.91 + free tier. SSM: bot/app/oauth
  + SLACK_NOTIFY_CHANNEL + SLACK_APPROVER_IDS + DASHBOARD_URL + PR write 4종. Canvas scope `canvases:write` 부여완료.

## Open Risks
- Slack/log/CloudWatch/kubectl/git/adapter-error input now enters through one `<untrusted_data>` boundary. The remaining
  risk is semantic prompt injection within that data, mitigated by tool-less L0 analysis and the permission/output gates.
- Never use credentials other than IAM Instance Profile (.env commits example only).
- EC2 always-on cost — verify EventBridge schedule stop/start.
- Non-goals (out of scope): public HTTPS endpoint, EC2 always-on, Level 2 (Execute), Production/deploy/IAM/DB changes,
  calling SQLite a prod datastore.
