# PROGRESS_LOG — slackops-devops-agent
Last updated: 2026-06-20

> Latest 3–5 increments (≤120 lines, newest on top). When it overflows, split into docs/archive/progress-YYYY-MM.md. Append via /checkpoint.
> Earlier entries (~2026-06-19): docs/archive/progress-2026-06.md

## 2026-06-27 — v2 Assistant flow end-to-end verification (자동) + run_user_message 분리
- Status: Done. 실 Slack 없이 **바인딩 전 흐름 자동 검증**. 실 워크스페이스 round-trip 은 여전히 미검증.
- Changed: assistant_handler `_user_message` 로직을 모듈레벨 **run_user_message** 로 추출(테스트 가능 바인딩 — 순수코어+얇은바인딩 원칙).
- Verified: 통합테스트(fake say/client + 실 store + 시뮬레이트 worker) — ① diagnose→DONE→결과 게시+**Canvas 생성**, ② pr→AWAITING_APPROVAL→
  **승인 버튼 게시**→클릭→**APPROVED 전이**. **실 slack_bolt 스모크**(importorskip): build_assistant→실 Assistant 생성, attach+register_approval_actions 실 App 배선(데코레이터/app.use/app.action 호환). `make check` **352 passed · ruff · mypy(35) · doc-budget**.
- Blockers: None. 잔여 리스크 = 실 버튼 클릭 payload 모양(container.message_ts/channel.id/actions[].value)·실 claude 스트리밍·Socket Mode 는 실 Slack 1회로만 확정.
- Next: 실 Slack sandbox e2e(앱 기동 `python -m app.main` + Assistant DM) → 이후 Modal/mock(D3)/실AWS(D4).

## 2026-06-26 — v2 pivot (AWSKRUG demo) + Slack Assistant approval gate + Canvas (D1/D2/D2.5)
- Status: Done (code+gate). Branch `v2`. **아직 실 Slack 미검증** — 다음은 sandbox e2e.
- Pivot: Slack 해커톤 제출 **폐기**(Devpost §3 Eligibility 원문 검증 — 한국 미포함, 일본 포함). 목표 = **AWSKRUG 발표 라이브 데모**.
  plan `docs/plans/2026-06-25-awskrug-demo.md`(rename from slack-challenge-v2). 기술축 = Slack Assistant + AWS MCP(검색 API 폐기). 90초 wow 시퀀스 박음.
- Changed: **assistant_handler**(D1, 기존) 위에 — **approval_actions.py**(승인 게이트 순수코어 decision_blocks/apply_decision + Bolt
  바인딩 register_approval_actions; web actions.ts 와 동일 store.approve/reject 낙관락 + audit, 멱등). **poll-in-thread**
  (poll_job/followup_for — 제안 job 정착까지 폴링 후 승인버튼/결과를 스레드 게시). **canvas.py**(postmortem_markdown +
  create_canvas; `canvases.create` scope canvases:write, 채널탭=Free팀 필수). assistant_handler.maybe_postmortem(완료 diagnose→
  포스트모템 Canvas). main 배선(store/audit/canvas_channel=SLACK_NOTIFY_CHANNEL 주입, try/except 안전). mcp_server 에 _dynamodb_from_env/audit_store_from_env.
- Verified: **Canvas 스파이크 라이브 통과**(워크스페이스 Hackathon, scope 추가+재설치 후 `canvases.create OK` canvas_id=F0BD7EQ1SJX).
  `make check` **349 passed · ruff · mypy(35) · doc-budget**. 실 Slack Assistant/버튼/poll UX 는 미검증.
- Blockers: None. (D2a=Assistant 턴 AWS MCP read 스트리밍은 uvx 의존 → 실 AWS D4 에 묶음.)
- Next: 실 Slack sandbox e2e(Assistant 스레드→제안→버튼→Canvas) · Modal diff승인 · mock 폴백(D3) · 실 AWS 1회(D4).

## 2026-06-20 — event-driven producer (EventBridge→Lambda) + Vercel live + cloud lifecycle + submission pack
- Status: Done. Full event-driven loop **live-verified on real AWS**; Vercel dashboard live; cost back to **$0**. Submission pack assembled. Next = 6/27 capture+submit.
- Changed: **`make cloud-*` lifecycle** (whoami/iam/ddb/up/status/console/ssm/schedule/start/stop/down + lambda-deploy/clean + vercel-key + alarm) wrapping `deploy/*.sh`; instance id → `deploy/.instance-id`. **main = working branch** (ff to hackathon-h0, 22 commits; user-data clones default branch). **i18n** diagnose + Tier1 `detect()` rationales → EN. **Event-driven producer** `src/app/alarm_lambda.py` + `deploy/lambda/{build,deploy,clean}.sh`: CloudWatch ALARM→EventBridge rule→Lambda(`detect()`→propose) into the **same DynamoDB queue** (serverless, fires EC2-off); `cloud-alarm.sh` rewritten event-driven. **Slack notifier** enabled via SSM `/slackops/SLACK_NOTIFY_CHANNEL` (+ `DASHBOARD_URL`). **Vercel** deployed (link + Team ID); `web/lib/ddb.ts` trim env + default region us-east-1 (paste-whitespace ValidationException fix). **`docs/submission/`** (renamed from ppt): `final_submission.md` (Devpost form), `schedule.md` (cost/judging), `PRESENTATION.md` (3-min script + Mac recording), `architecture.md`+png (event path), items/tables.png.
- Verified: `make check` **316 passed** · ruff · mypy(32) · doc-budget. **Live e2e on EC2 (t3.medium)**: CloudWatch ALARM→EventBridge→Lambda(07:51 CW logs)→DynamoDB proposal→worker(Claude)→DONE→Slack ping+done **$0.15/2.7K–6K tok**; diagnose real CloudWatch via Instance Profile (write→denied). Vercel dashboard live on real DynamoDB. **EC2 terminated + demo alarm deleted → cost ≈ $0** (DynamoDB/Vercel/Lambda/EventBridge/SSM kept).
- Blockers: None. (detect iam needs accessanalyzer perms + an analyzer — secondary/optional.)
- Next: **6/27~28** `make cloud-up`(SSM auto-applies all 5 params) → record video (PRESENTATION slide 11) → `cloud-stop` → Devpost submit (deadline 6/30 09:00). `final_submission` own-voice edit + bonus article.

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
