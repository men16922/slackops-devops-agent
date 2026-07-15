# STATUS — slackops-devops-agent
Last updated: 2026-07-15

> Current state/verification/risks (≤120 lines). Source of truth. Update via /checkpoint.

## Current summary
- Day 1–3 **local implementation complete**: Socket Mode routing + `/devops ping` + job queue + permission gate
  + FastAPI health/metrics. deploy/ artifacts (IAM/EC2/EventBridge/ADOT) ready-to-run.
- AWS/Slack **cloud deploy A–C verified once** (2026-06-20): Slack App + SSM tokens + IAM + DynamoDB(us-east-1) + EC2 →
  `/devops ping` pong from `ip-…ec2.internal`. EC2 then terminated (cost ~$0). Runbook docs/runbooks/deploy-checklist.md.
- **D15 secure runtime production deployed (2026-07-15):** GitHub OAuth boundary, immutable execution-plan/approval hash,
  workspace/tool-chain/postcondition validation, approver allowlist/audit chain/EC2 hardening; Vercel and real GitHub login passed.

## Verification Baseline
- 3-layer gate: `make check` → **392 passed** · `ruff` · `mypy src`(strict) · documentation-budget gate all green;
  `cd web && npm run build` and `git diff --check` also pass for D15.
- **Event-driven loop live (2026-06-20, real AWS):** CloudWatch ALARM→EventBridge rule→Lambda(`alarm_lambda`, detect→propose)
  →DynamoDB queue→worker(Claude)→DONE→Slack ping+done ($0.15/2.7K–6K tok). Serverless producer fires EC2-off. Then EC2 terminated → cost ≈ $0.
- **Vercel dashboard live** on real DynamoDB (link + Team ID captured); `web/lib/ddb.ts` trims env + default region us-east-1.
  D15 GitHub OAuth and required allowlist are now deployed to Production; unauthenticated `/` redirects to `/login`.
- **D16 secure read-adapter hardening (2026-07-15):** logs/diagnose/detect no longer expose generic AWS API MCP to Claude.
  Fixed boto3 read adapters collect only command-specific evidence, then sanitizer isolates it; model tool allowlists are empty.
  Runtime drops the AWS MCP/uvx dependency, unused S3 access, broad SSM enumeration, and child Slack/dashboard secrets.
- **D17 role/metadata/egress hardening (real EC2 rehearsal, 2026-07-15):** fresh instance verified 1-hour runtime/MCP STS roles,
  forced credential rotation, fixed AWS read IAM, four services/timer, IMDS/direct-egress denial, GitHub proxy allow and unlisted-domain deny.
  MCP `ping` proposal produced `proposed→claimed→done` audit evidence; instance stopped and temporary source artifact removed. Rehearsal fixed
  the DynamoDB policy region ARN, Squid duplicate-domain ACL, and user-data archive branch; generic AWS MCP remains retired.
- **P1 central system-boundary audit (real EC2 rehearsal, 2026-07-15):** deployment operator provisions the 30-day
  `/slackops/security-boundary-audit` group; a root-only audit STS role can create streams/append only. Runtime/MCP cannot
  write it (runtime `PutLogEvents` produced explicit deny). Fresh EC2 logged `credential_refresh` and URL-free
  `proxy_denied` events; audit env is root `600`, state is root `700`, and the source artifact/instance were removed/stopped.
- **All user-facing text English** (H0): Playwright verified, except two Korean seed rationales (`agent-2001/2002`) now exposed by Proposal; translate them.
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
  **UI 리디자인(2026-07-10, `35f4b38`)**: AWS 콘솔/Datadog 감성 라이트 테마 — KPI 스탯 타일, STATUS(pill+dot)↔SOURCE(플랫 태그) 형태 분리,
  제브라/tabular 테이블, Chat=ops 콘솔 카드, ARGS→Proposal 컬럼, LIVE·연결 상태 칩, 이모지 제거·벨 SVG화. `next build` green.
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
  (`/api/jobs/agent-pending`) + governance `detect` scan-as-job (fixed AWS read adapters; iam/config/ssm/incident,
  L0) + Detections menu (`/detections` ON/OFF + Scan now, toggles in `CONFIG#detections`). All gated (310 passed,
  next build green). Real scan findings = cloud-only (EC2+IAM). Reframe: triage/safe-response layer over existing signals.

## Active Focus
- **v2 = AWSKRUG 발표 데모** (branch `v2`, plan `docs/plans/2026-06-25-awskrug-demo.md`). Slack 해커톤 제출 **폐기**(Devpost §3
  Eligibility 한국 미달). 목표 = "Slack 자연어 → 실 AWS 안전 진단 → 승인게이트 → 포스트모템 Canvas" 라이브 데모(보안+관측성 차별점).
- **D1–D3 + 실 Slack sandbox e2e 완료(359 passed, 2026-07-02)** — Assistant 승인게이트/Canvas/mock 폴백에 더해 **실 워크스페이스
  라이브 통과**: 일반 DM 폴백(register_dm_messages — ✨ 패널은 유료 표면) 경로로 스트리밍→pr 제안→diff+버튼→approved 전이
  (audit via slack)→**채널 탭 Canvas 자동 생성**→footer/payload 확정. manifest(events+messages_tab+im:history) 정비,
  ASSISTANT_POLL_TIMEOUT_S(240s). **D4 실 AWS 검증 완료(2026-07-06)**: EC2→CloudWatch 진단+write-denied. ★ NEXT = 슬라이드 디자인 마무리.
  pr execute(실 push)는 로컬 생략 — 발표 시 EC2 라이브. (선택) Modal diff·Message Shortcut 은 미구현 BUY 잔여.
- H0 인프라(DynamoDB/Vercel/Lambda/SSM)는 그대로 유지, **비용 ≈ $0**. AWS credit rejected → $63.91 + free tier.
  SSM: bot/app/oauth + SLACK_NOTIFY_CHANNEL(+canvas 대상 채널) + DASHBOARD_URL. Canvas scope `canvases:write` 부여완료.

## Open Risks
- Slack/log/CloudWatch/kubectl/git/adapter-error input now enters through one `<untrusted_data>` boundary. The remaining
  risk is semantic prompt injection within that data, mitigated by tool-less L0 analysis and the permission/output gates.
- Never use credentials other than IAM Instance Profile (.env commits example only).
- EC2 always-on cost — verify EventBridge schedule stop/start.
- Non-goals (out of scope): public HTTPS endpoint, EC2 always-on, Level 2 (Execute), Production/deploy/IAM/DB changes,
  calling SQLite a prod datastore.
