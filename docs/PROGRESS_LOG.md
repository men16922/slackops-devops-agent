# PROGRESS_LOG — slackops-devops-agent
Last updated: 2026-06-20

> Latest 3–5 increments (≤120 lines, newest on top). When it overflows, split into docs/archive/progress-YYYY-MM.md. Append via /checkpoint.
> Earlier entries (~2026-06-19): docs/archive/progress-2026-06.md

## 2026-06-20 — local e2e verified + Slack/detect/notifications + cloud-alarm + local DX
- Status: Done. F1–F5 로컬 e2e 라이브 검증 + Slack 라이브 + cloud-alarm 시나리오. 다음 = 클라우드.
- Changed: Slack `/devops detect` 동기 경로 등록(usage 갱신); 알림을 **작업 생명주기 이벤트**로 일반화
  (new/awaiting/done/failed, source 라벨 — web/agent/slack 활동·완료를 채널 인지) + notifier 로그(started/
  disabled/post_failed); **UI fix** 이모지 단축코드(:mag:→🔍) 렌더 + `AutoRefresh`(작업 피드 4s 자동갱신) +
  프롬프트 Markdown(## 헤딩/**bold**); **비용 안전** Config 기본 OFF + paid 플래그(roadmap 미배선=호출불가);
  **로컬 DX** `make install`/`.env` 자동로드/`make demo-all`·`slack`/`make demo-incident`; **`make cloud-alarm`**
  (+clean) 실 alarm 강제→agent diagnose 제안(EventBridge 자동=roadmap, 이 타깃이 다리); mypy override
  app.slack_handler(slack_bolt 스텁부재 환경의존 제거). Docs: features/DEVPOST/DEMO_SCRIPT/PRESENTATION/
  architecture; QA→클라우드-only 체크리스트.
- Verified: `make check` **310 passed** · ruff · mypy(31) · doc-budget / web `next build`. **Playwright UI e2e**
  (벨·Detections·Scan-now·승인). **실 Claude L0**(diagnose done $0.14). **Slack 라이브**(`/devops ping` + 생명주기
  알림 incl. 스케줄러 iam 스캔). cloud-alarm/cloud DX = `bash -n` OK(실 AWS 미실행).
- Blockers: None.
- Next: 클라우드(EC2) — diagnose/scan findings · write-denied · DynamoDB screenshot · `make cloud-alarm` · Vercel(링크/Team ID).

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
