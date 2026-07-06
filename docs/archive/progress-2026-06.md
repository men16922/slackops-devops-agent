# PROGRESS_LOG archive — 2026-06
최종 갱신: 2026-07-02

> docs/PROGRESS_LOG.md 예산(≤120줄) 초과로 분리된 원문 (최신이 위). 현재 증분은 docs/PROGRESS_LOG.md.

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

## 2026-06-13 — 리뷰 findings 환류: store 유틸 통합 + stale 주석 (로컬 [auto] 소진)
- Status: 완료. **NEXT_PLAN [auto] 전부 소진** — 잔여는 [manual] 트랙만.
- Changed: store/_util.py 신규(utcnow_iso/day_of/encode_for_dynamodb) — sqlite/dynamodb/
  audit/telemetry 4개 store 의 중복 정의 제거(기존 이름 alias import 로 call site 무변경).
  main.py /metrics 주석을 현 상태로 갱신(수집은 TelemetryStore/OTel, endpoint 는 liveness).
  worker.process_one 에 pr 의 prepare/execute 2회 metric 기록이 의도임을 명시.
- Verified: pytest 229 passed, 1 skipped(**테스트 무수정** = 동작 불변) + ruff/mypy green.
- Blockers: 없음.
- Next: [manual]만 — 크레딧 → Slack App+deploy → ping e2e → provision → 대시보드 → 제출물.

## 2026-06-13 — Day 9.5 품질 리뷰 회차 (read-only, 2관점 병렬)
- Status: 완료. 코드 무수정 — findings 환류만(리뷰 회차 패턴 첫 실사용).
- Changed: docs 만. NEXT_PLAN Day 9.5 를 findings 환류 [auto] 1건으로 교체(store 유틸 통합
  + stale 주석 정리). 리뷰 범위 = src/app 전체(H0 milestone 산출물).
- Verified(리뷰 결과): **보안(주입 방어 우회) 관점 clean** — 4계층(sanitizer 태그 위조/argv
  플래그 주입/allowlist 좁히기/출력 게이트) 우회 불발견. 품질 관점 10건 보고 중 채택 2건
  (store 4곳 _utcnow_iso/_day_of/_encode 중복, main.py /metrics stale 주석), 기각 다수
  — tool_calls None(stream-json 전 의도)·게이트 거부 미계측(테스트로 강제한 설계)·
  Decimal 왕복·tracer=None silent skip(전부 기존 결정/문서화됨).
- Blockers: 없음.
- Next: [auto] 잔여 = Day 9.5 findings 환류 1건. 이후 [auto] 소진 — [manual] 트랙만.

## 2026-06-13 — claude_runner·commands telemetry 계측 결합 (Day 8–9 [auto] 완결)
- Status: 완료. H0 로컬 [auto] Observability 마지막 항목 — 호출 계측이 끊기던 갭 해소
  (핸들러가 문자열만 반환해 RunResult 의 tokens/cost 가 유실되던 구조).
- Changed: telemetry.py RunMetrics(frozen)+RunMetricsHook. allowlist.run_for_command 에
  on_metrics — 모든 Claude 호출의 단일 진입점에서 duration/tokens/cost/success emit
  (실행기 예외도 success=False emit 후 재전파, 게이트 거부는 호출 아님 — 미계측).
  commands/{logs,diagnose,tf_review,pr} on_metrics passthrough(pr 은 prepare/execute 양쪽).
  worker.default_executors — hook capture 로 실 tokens/cost 를 CommandOutcome 에 병합
  (complete()의 job.cost_usd 에도 실림), Worker(tracer=...) 주입 시 metric write-back 이
  OTel span 으로도 emit. tests +9(allowlist hook 3종/핸들러 passthrough 4종/worker 2종).
- Verified: `python3 -m pytest tests/ -q` → 229 passed, 1 skipped. ruff/mypy green.
- Blockers: 없음. tool_calls 는 여전히 None(stream-json 파싱 도입 전 — 기존 결정 유지).
- Next: [auto] Day 9.5 품질 리뷰 회차. [manual] ADOT Collector + 실측 캡처.

## 2026-06-13 — telemetry.py OTel 파이프라인 (setup_telemetry 실 구현 + span emit)
- Status: 완료. Day 8–9 [auto] 1번 — store 가 source of truth 인 채로 OTel 을 부가 emit 으로 결합.
- Changed: src/app/telemetry.py — setup_telemetry 실 구현(TracerProvider + Resource service.name
  + SimpleSpanProcessor(저볼륨·짧은 수명 프로세스라 동기 export — batch flush 유실 없음);
  exporter 주입 가능, 미주입이면 OTLP gRPC lazy(기본 127.0.0.1:4317 ADOT), SDK/exporter
  미설치면 None). record_run_metrics 에 tracer 키워드 — 주입 시 "devops.run" span 으로
  지표 emit(None 지표는 속성 생략), store 기록은 불변. pyproject mypy override 에
  opentelemetry.exporter.* 추가(로컬 미설치 lazy dep). tests/test_telemetry.py +4
  (in-memory exporter 파이프라인/span 속성/실패 error/None 생략 — SDK 미설치 시 skip).
- Verified: `python3 -m pytest tests/ -q` → 220 passed, 1 skipped. ruff/mypy green.
- Blockers: 없음. 실 OTLP/ADOT 송신은 [manual](EC2 ADOT Collector 구성) 에서 검증.
- Next: [auto] claude_runner·commands telemetry 계측 결합.

## 2026-06-13 — 하네스 개선 5/5: 품질 리뷰 회차 패턴 (NEXT_PLAN 체인)
- Status: 완료. 개선안 5번 — "구현→리뷰→수정" 품질 루프를 1회차=1작업 불변과 호환되게 체인.
- Changed: docs/NEXT_PLAN.md Day 9.5 신설 — `[auto]` 리뷰 회차(H0 milestone range read-only
  리뷰, 보안/타입/단순화 관점, 코드 수정 금지, findings 는 `[auto]` 환류). LOOP_ENGINEERING
  §3.4 에 품질 리뷰 회차 패턴 문서화. 실소비 검증은 다음 overnight 가동에서.
- Verified: `python3 -m pytest tests/ -q` → 216 passed, 1 skipped. ruff/mypy green(최종 일괄 실측).
- Blockers: 없음.
- Next: 개선안 5건 완료 — 다음 overnight 가동으로 실전 검증. [auto] 잔여 = Day 8–9 OTel → Day 9.5 리뷰.

## 2026-06-13 — 하네스 개선 4/5: iter 로그 보존 정책 (KEEP_ITER_LOGS)
- Status: 완료. 개선안 4번 — 장기 가동 시 iter-*.log 무한 증식 통제.
- Changed: bin/overnight/run.sh — prune_iter_logs(회차 시작 시 `iter-*.log` 최근
  `KEEP_ITER_LOGS`(기본 30)개만 유지, 파일명이 타임스탬프라 sort -r = 최신순; runner.log 는
  항상 보존). LOOP_ENGINEERING §3.1 표 갱신.
- Verified: `bash -n` clean. 더미 5개 + KEEP=3 실측 → 최신 3개만 잔존, runner.log 무영향.
- Blockers: 없음.
- Next: 개선 5 — NEXT_PLAN 품질 리뷰 회차 패턴.

## 2026-06-13 — 하네스 개선 3/5: 반복 Blocker 전략 적응 ([blocked] 태그)
- Status: 완료. 개선안 3번 — 막힌 작업 1개가 백로그 전체를 잠그는 것 방지(러너 백스톱은 "멈춤"만,
  이건 "건너뛰고 계속").
- Changed: bin/overnight/PROMPT.md 3단계 — 선택 전 PROGRESS_LOG Blocker 이력 확인, 같은 항목
  2회면 NEXT_PLAN 에 `[blocked]` 마킹(사유 1줄) 후 다음 후보로; 전부 blocked/소진이면 DONE(사유
  구분). NEXT_PLAN 헤더·LOOP_ENGINEERING §3.3/§3.4 에 `[blocked]` 규약 추가.
- Verified: `python3 -m pytest tests/ -q` → 216 passed, 1 skipped(문서 변경 무회귀).
- Blockers: 없음.
- Next: 개선 4 — run.sh iter 로그 보존 정책.

## 2026-06-13 — 하네스 개선 2/5: 러너 no-progress 백스톱 (HEAD 전후 비교)
- Status: 완료. 개선안 2번 — "success+커밋 없음" 무진행 루프를 consec_fail 이 못 잡는 맹점 차단.
- Changed: bin/overnight/run.sh — 회차 전 `git rev-parse HEAD` 기록, success 분기에서 HEAD 불변이면
  no_progress++(`MAX_NO_PROGRESS` 기본 2 도달 시 안전 중단), 새 커밋이면 리셋. DONE/STOP 생성
  회차는 루프 상단 파일 검사가 먼저 종료하므로 충돌 없음. LOOP_ENGINEERING §3.1 표/§3.2/§4 갱신.
- Verified: `bash -n run.sh` clean. 분기 데스크체크(STOP/DONE 선행, limit 분기는 카운터 무영향).
- Blockers: 없음.
- Next: 개선 3 — 반복 Blocker `[blocked]` 태그 전략 적응.

## 2026-06-13 — 하네스 개선 1/5: 커밋 게이트 3계층화 (pytest + ruff + mypy)
- Status: 완료. 루프 개선안(plans/cozy-munching-newt) 1번 — 검증 밀도 확장.
- Changed: pyproject.toml mypy overrides(boto3/botocore/slack_bolt/fastapi stub 부재 한정
  ignore_missing_imports + app.main 데코레이터 완화 — 실 타입 검사 약화 아님, 미설치 환경 noise 제거).
  bin/overnight/PROMPT.md 4단계 게이트 = pytest + `ruff check src tests` + `mypy src` 전부 green.
  skills/{checkpoint,overnight-report}/SKILL.md 검증 명령 동기화. LOOP_ENGINEERING §2/§3.3.
- Verified: `python3 -m pytest tests/ -q` → 216 passed, 1 skipped. `ruff check src tests` clean.
  `mypy src` → Success: no issues in 22 files (13 errors → 0, 전부 stub noise 였음).
- Blockers: 없음.
- Next: 개선 2 — run.sh no-progress 백스톱(HEAD 비교).

## 2026-06-12 — 하네스 개선: overnight 회차 시작 시 잔여물(dirty tree) 자동 복구 단계
- Status: 완료. 제품 코드 변경 없음 — LOOP 하네스 자체 개선 1건(예측가능성/복구가능성).
- Changed: bin/overnight/PROMPT.md 절차에 2단계 "잔여물 복구" 추가(이하 6단계로 재번호) —
  회차 시작 시 `git status --porcelain` 검사; dirty 면 복구가 그 회차의 작업 1묶음:
  pytest green → `[recovered]` 커밋 직행, red → 무수정 + Blocker 기록 + STOP 생성(사람 검수,
  graceful 정지). 근거: 2026-06-12 commit 직전 session limit 중단 → 수동 복구했던 사례의
  자동화 + 다음 회차 `git add -A` 가 미검증 잔여물을 새 커밋에 섞는 오염 차단.
  docs/LOOP_ENGINEERING.md §3.3(6단계 절차)/§5(한계 — 복구 자동화 반영) 동기 갱신.
- Verified: `python3 -m pytest tests/ -q` → 216 passed, 1 skipped(baseline 불변).
  현재 트리 clean + bin/overnight/{logs,STOP,DONE} gitignore 확인(dirty 신호 신뢰성 전제).
- Blockers: settings.json 에 `git stash push` allowlist 추가는 auto mode 분류기가 거부
  (self-modification 권한 확장) → red 잔여물은 stash 보존 대신 무수정+STOP 방식으로 적응
  (더 보수적 — 파괴/권한확장 없음). 권한 확장이 필요해지면 사용자 승인으로만.
- Next: 다음 하네스 개선 후보 = 동일 작업 반복 Blocker 감지(같은 [auto] 항목이 2회 이상
  Blocker 면 건너뛰기/중단 판단). 제품 [auto] 잔여 = Day 8–9 telemetry OTel.

## 2026-06-12 — commands/{tf_review,pr} 구현 + pr 출력게이트 worker 연결 (overnight 회차)
- Status: 완료. H0 트랙 [auto] 마지막 항목 — Day 6–7 [auto] 2건도 함께 충족(같은 작업의 상세 기준).
- Changed: commands/tf_review.py(handle_tf_review — PlanFetcher 주입(기본 = TF_PLAN_ARGS 고정
  `terraform plan -no-color -input=false -lock=false`, apply 불가), plan 격리 → 위험/비용/보안
  리뷰 프롬프트 → run_for_command). commands/pr.py(handle_pr 2단계 — prepare: PR_GATED_TOOLS
  (`git push`/`gh pr create`) 를 argv 에서 제거 + 마커(===DIFF_BEGIN/END===)로 diff 추출 →
  PrResult.diff, execute(approved_diff 전달 시): 전체 allowlist 로 push+PR; 설명은 검증
  (비어있지 않음/≤2000자) 후 격리 블록으로만 전달). allowlist.run_for_command 에
  exclude_tools(좁히기 전용) 추가. worker.default_executors — pr_executor(approved_by 있으면
  job.diff 를 approved_diff 로 전달, PrResult→CommandOutcome.diff 연결), tf-review 에 runner
  전달. slack_handler.register_default_commands 에 tf-review 등록(pr 은 동기 경로 의도적
  미등록 — 게이트가 store 상태 요구, worker 경유 전용). tests: test_tf_review_command.py 9종
  (조립/allowlist argv/apply 부재(argv+기본 fetcher)/빈 plan/실행 실패/태그 위조 무력화),
  test_pr_command.py 13종(prepare 게이트 도구 부재 = 게이트 없이 PR 생성 불가, 격리/위조,
  마커 파서, execute 전체 allowlist, 입력 검증), test_worker.py +2(default_executors pr e2e —
  prepare 게이트→approve→execute argv 검증, tf-review e2e), test_slack_routing.py 갱신.
- Verified: `python3 -m pytest tests/ -q` → 216 passed, 1 skipped. `python3 -m ruff check`
  변경 9파일 clean.
- Blockers: 없음.
- Next: [auto] 잔여 = Day 8–9 telemetry OTel 파이프라인 + 계측 결합. [manual] = v0 대시보드/크레딧/provision.

## 2026-06-12 — worker.py 폴링 루프 (claim→실행→게이트/complete + write-back, overnight 회차)
- Status: 완료. H0 트랙 [auto] 3번 항목 — 이중 컨트롤플레인 consumer 골격.
- Changed: src/app/worker.py 신규 — Worker(job/audit/telemetry store 주입, process_one =
  claim→executor 실행→outcome.diff 있고 미승인이면 await_approval(출력 게이트), 아니면
  complete(DONE), 예외는 FAILED — 모두 audit append + record_run_metrics write-back),
  run_forever(주입 sleep/max_iterations 폴링), CommandOutcome(result/diff/tokens/cost_usd/
  tool_calls), default_executors(ping/logs/diagnose/tf-review/pr — 호출 시점 모듈 조회,
  runner 전달; tf-review/pr 은 현 스텁이 NotImplementedError → FAILED 경로),
  매핑 외 명령은 실행 없이 FAILED(default deny). tests/test_worker.py 9종(빈 큐/폴링 sleep,
  logs e2e mock runner+fetcher → DONE+audit[claimed,done]+metric, ping default_executors,
  주입 monotonic duration_ms, pr diff → AWAITING_APPROVAL 게이트, approve 후 재claim →
  게이트 재진입 없이 DONE, executor 예외 → FAILED+metric success=False, 미정의 명령 거부).
- Verified: `python3 -m pytest tests/ -q` → 192 passed, 1 skipped. `python3 -m ruff check`
  신규 2파일 clean.
- Blockers: 없음.
- Next: [auto] commands/{tf_review,pr}.py 구현(pr 출력게이트 = CommandOutcome.diff 연결).

## 2026-06-12 — telemetry.py record_run_metrics → TelemetryStore (overnight 회차)
- Status: 완료. H0 트랙 [auto] 2번 항목 — telemetry 가 store 레이어를 소비하는 첫 결합.
- Changed: src/app/telemetry.py 재작성 — record_run_metrics(store, job_id, *, command/duration_ms/
  tokens/cost_usd/tool_calls/success/error) 가 주입된 TelemetryStore.record 에 위임(MetricRecord 반환).
  구 시그니처(step_latencies_ms/failed)는 store 스키마(duration_ms/success)로 정렬. setup_telemetry 는
  lazy stub 로 전환 — opentelemetry lazy import, 미설치면 None(기존 NotImplementedError 제거).
  tests/test_telemetry.py 신규 5종(주입 store 기록 roundtrip, 실패 error 보존, 기본값, 일자 피드 노출,
  setup_telemetry import-safe).
- Verified: `python3 -m pytest tests/ -q` → 183 passed, 1 skipped. `ruff check` 신규/변경 파일 clean.
  `mypy src/app/telemetry.py` — telemetry 자체 오류 0(잔여는 기존 boto3 stub 부재 noise).
- Blockers: 없음.
- Next: [auto] worker.py 폴링 루프(claim→run_for_command→complete/await_approval+audit/metric write-back).

## 2026-06-12 — AuditStore + TelemetryStore (단일테이블 Audit/Metric 항목, overnight 회차)
- Status: 완료. H0 트랙 [auto] 1번 항목 — store 레이어 확장.
- Changed: src/app/store/audit_store.py(AuditEvent/AuditStore 프로토콜 + Sqlite/DynamoDb 구현 —
  PK=JOB#{id}, SK=AUDIT#{ts}#{seq:06d}, GSI2=AUDIT#{yyyymmdd}/{ts}, seq 는 같은 ts tie-breaker),
  src/app/store/telemetry_store.py(MetricRecord/TelemetryStore + 양 구현 — SK=METRIC#{ts},
  GSI2=METRIC#{yyyymmdd}/{ts}, float→Decimal 변환), app.store __init__ 에서 신규 + DynamoDbJobStore
  export. tests/_helpers.py 로 counter_clock/counter_id/create_single_table 공용화(test_store 중복 제거).
- Verified: `python3 -m pytest tests/ -q` → 178 passed, 1 skipped(+25: 동치 12종×2 — append/record
  roundtrip, 시간순/limit, job 스코프, 일자 피드 최신순/필터, 같은 ts seq 정렬 + 단일테이블 공존 1종).
  `ruff check` 변경 파일 clean.
- Blockers: 없음.
- Next: [auto] telemetry.py(record_run_metrics→TelemetryStore) → worker.py 폴링 루프.

## 2026-06-12 — H0 해커톤 피벗 D1–D2 (DynamoDB store 레이어)
- Status: 진행 중. 브랜치 hackathon-h0. 데이터층 핵심(JobStore) 완료.
- Changed: DECISIONS D5(피벗) + docs/plans/2026-06-12-h0-hackathon.md + NEXT_PLAN active 트랙.
  src/app/store/{base,sqlite_store,dynamodb_store}.py — JobStore 프로토콜 + 이중 구현(상태머신
  PENDING→AWAITING_APPROVAL→APPROVED→RUNNING→DONE|FAILED, claim 원자성, 출력 게이트).
  레거시 job_queue.py 대체. pyproject moto dev dep.
- Verified: `python3 -m pytest tests/ -q` → 153 passed, 1 skipped. test_store.py 22종(SQLite +
  moto DynamoDB 동치 — claim FIFO/우선순위/중복방지, 승인 플로우, reject).
- Blockers: 없음. AWS 크레딧/v0 계정/실 테이블 provision 은 [manual] 선행 대기.
- Next: AuditStore/TelemetryStore + slack_handler route→enqueue 전환 → worker.py(claim→run→write-back).

## 2026-06-12 — code-review 후속 수정 (밤샘 산출물 10 findings 일괄 수정)
- Status: 완료. high-effort 멀티에이전트 리뷰가 찾은 버그 5 + 정리 5 를 우선순위대로 수정.
- Changed:
  - #1+#8 slack_handler.route: 핸들러 예외(ClaudeTimeout/Permission/Allowlist/일반)를 Slack
    메시지로 매핑하는 최종 안전망(무응답 silent crash 제거) + commands/_replies.py 로 에러문구 일원화.
  - #3 sanitizer._TAG_FORGERY: 닫는 '>' 없는 미완성 태그도 무력화(`[^>]*>?`) — 부분 close 위조 차단.
  - #4 logs._SERVICE_RE: 선행 '-' 거부 + diagnose fetch_kubectl_describe argv 에 '--' 구분자.
  - #5 logs.fetch_cloudwatch_logs: filter_log_events(가장 오래된 것)→describe_log_streams
    +get_log_events(startFromHead=False)로 **최신** 이벤트 조회.
  - #6 bin/overnight/run.sh: limit 감지를 --output-format json 의 is_error 우선 판정으로
    교체(성공 회차의 'rate limit' 언급 오판 제거) — classify_outcome(python3).
  - #7 permissions.COMMAND_SPECS 단일 레지스트리 + allowlist._cross_check_with_permissions
    import-time 강제(4곳 드리프트→import 에러).
  - #9 tests/_helpers.py 로 RecordingRunner/RecordingFetcher/result_json 일원화(4파일 중복 제거).
  - #10 RunResult.tool_calls 죽은 필드(항상 0·무참조) 제거.
- Verified: `python3 -m pytest tests/ -q` → 133 passed, 1 skipped(fastapi 로컬 미설치).
  새 검증 9종(미완성 태그·선행 dash·kubectl '--'·route 예외매핑 4·allowlist↔permissions 불변).
  run.sh classify_outcome 4케이스 수동 검증(성공/limit/failure/non-json).
- Blockers: 없음.
- Next: Day 6–7 [auto] — commands/tf_review.py, commands/pr.py(출력 게이트).

## 2026-06-12 — slack_handler 에 logs/diagnose 라우팅 등록 (Day 4–5 완결, overnight 회차)
- Status: 완료. Day 4–5 트랙 마지막 항목 — register_default_commands 에 logs/diagnose 연결.
- Changed: src/app/slack_handler.py(register_default_commands: `from app.commands import
  diagnose, logs, ping` 후 호출 시점 모듈 속성 조회 lambda 로 ping/logs/diagnose 등록 —
  monkeypatch 주입 가능). tests/test_slack_routing.py(+4: logs/diagnose 라우팅·인자 전달,
  인자 없는 logs/diagnose 는 service 검증에서 fetcher/Claude 호출 전 거부; 기존
  "미구현" 테스트는 tf-review 로 이전). 추가 수정 — 기존 테스트 오염 발견·해소:
  test_logs/diagnose_command 의 importlib.reload 가 모듈 dict 를 제자리 갱신해
  타 모듈이 든 InvalidServiceName 클래스 정체성을 깨뜨림(구 validated_service 가 런타임
  전역 조회로 신 클래스를 raise → diagnose 의 except 미스매치). import-safety 테스트를
  sys.modules 를 건드리지 않는 fresh copy(module_from_spec+exec_module) 방식으로 교체.
- Verified: `python3 -m pytest tests/ -q` → 124 passed, 1 skipped(fastapi 미설치 로컬 한정).
  2회 연속 실행으로 순서 의존 재발 없음 확인.
- Blockers: 없음.
- Next: NEXT_PLAN 다음 [auto] — commands/tf_review.py(terraform plan 실행기 주입 mock,
  plan 출력 격리, apply 경로 부재 확인 테스트).

## 2026-06-11 — commands/diagnose.py 구현 (다중 소스 종합 진단 조립, overnight 회차)
- Status: 완료. Day 4–5 트랙 다섯 번째 항목 — diagnose 핸들러(다중 소스 수집기 주입 + 격리 결합).
- Changed: src/app/commands/diagnose.py(handle_diagnose: fetchers 매핑 주입(SourceFetcher) →
  collect_sources(소스별 실패 격리 — fetcher 예외도 untrusted 데이터로 격리 블록에 기록) →
  combine_sources(`=== source: ... ===` 섹션 마커, 빈 소스 `(no data)` 표기) → build_prompt
  단일 격리 블록 → run_for_command("diagnose"); 기본 수집기 3종 — fetch_cloudwatch_logs 재사용
  + fetch_kubectl_describe + fetch_git_diff(log -10 + diff HEAD~1), 전부 호출 시점에만 외부
  도구 사용; 전 소스 빈 데이터 시 Claude 미호출). src/app/commands/logs.py(_validated_service
  → validated_service 공개 승격 — diagnose 와 service 검증 공유, 동작 동일).
  tests/test_diagnose_command.py 15종(다중 소스 조립/단일 격리 블록/태그 위조 무력화/섹션
  라벨/service 주입 거부/fetcher 실패 격리/(no data)·전체 빈 데이터·exit≠0 경계/순서 보존/
  import-safe). AWS/kubectl/git 실 호출 없음.
- Verified: `python3 -m pytest tests/ -q` → 120 passed, 1 skipped(fastapi 미설치 로컬 한정).
- Blockers: 없음.
- Next: NEXT_PLAN 다음 [auto] — slack_handler 에 logs/diagnose 라우팅 등록
  (register_default_commands).

## 2026-06-11 — commands/logs.py 구현 (CloudWatch 조회+분석 조립, overnight 회차)
- Status: 완료. Day 4–5 트랙 네 번째 항목 — logs 핸들러(조회→격리→실행 조립).
- Changed: src/app/commands/logs.py(handle_logs: fetcher 주입(LogFetcher) → sanitizer
  build_prompt 격리 → run_for_command 조립, 빈 로그/비정상 exit 는 안내 메시지;
  _validated_service: Slack untrusted 인자를 log group 문자 집합 regex 로 강제 검증 후에만
  template 삽입(주입 방어 4계층); LOGS_PROMPT_TEMPLATE: `{untrusted_data}` placeholder 신뢰
  template; fetch_cloudwatch_logs: boto3 lazy import 기본 fetcher — filter_log_events
  paginator, MaxItems 상한). tests/test_logs_command.py 12종(조립/태그 격리·위조 무력화/
  service 인자 주입 거부/빈 로그·exit≠0 경계/이중 확장 방지/lazy import). AWS 실 호출 없음.
- Verified: `python3 -m pytest tests/ -q` → 105 passed, 1 skipped(fastapi 미설치 로컬 한정).
- Blockers: 없음. (참고: template 본문에 raw `<untrusted_data>` 태그 언급 시 build_prompt 가
  거부 — 문구를 태그 없는 표현으로 작성해야 함.)
- Next: NEXT_PLAN 다음 [auto] — commands/diagnose.py(다중 소스 수집기 주입 + 격리 결합).

## 2026-06-11 — allowlist.py 구현 (Tool Allowlist 주입 방어 2계층, overnight 회차)
- Status: 완료. Day 4–5 트랙 세 번째 항목 — 명령별 Tool Allowlist 매핑 + claude_runner 연결점.
- Changed: src/app/allowlist.py(_COMMAND_TOOLS: logs/diagnose/tf-review/pr → `--allowedTools`
  패턴 매핑, ping 은 Claude 미경유라 의도적 제외; allowed_tools: default deny + 복사본 반환;
  validate_mapping: FORBIDDEN_ACTIONS 키워드 단어 단위 regex 로 매핑 자체를 import 시 검증;
  run_for_command: permissions.is_allowed 게이트 → allowlist → run_headless 단일 진입점,
  거부 시 subprocess 미실행). tests/test_allowlist.py 17종(매핑/default deny/ping 제외/
  복사본/금지 키워드 전수 스캔/validate 거부 케이스/runner 연결·거부 시 미호출).
- Verified: `python3 -m pytest tests/ -q` → 93 passed, 1 skipped(fastapi 미설치 로컬 한정).
- Blockers: 없음.
- Next: NEXT_PLAN 다음 [auto] — commands/logs.py(CloudWatch 주입 mock + sanitizer 격리 +
  run_for_command 조립).

## 2026-06-11 — claude_runner.py 구현 (Headless subprocess wrapper, overnight 회차)
- Status: 완료. Day 4–5 트랙 두 번째 항목 — run_headless + RunResult 파싱.
- Changed: src/app/claude_runner.py(build_command: `claude -p --output-format json` 인자 리스트
  shell 미사용, allowlist 비면 `--allowedTools` 생략=default deny; run_headless: SubprocessRunner
  주입(테스트 mock/실 subprocess), TimeoutExpired→ClaudeTimeoutError; _parse_result: result JSON 의
  result/usage 토큰합/total_cost_usd 파싱, 비-JSON 은 raw fallback, 실패는 exit_code 로 전달).
  tests/test_claude_runner.py 14종(성공 JSON/raw fallback/부분 usage/비수치 cost/실패 stderr/
  timeout/인자 전달/shell 미사용). 실 `claude` 호출 없음.
- Verified: `python3 -m pytest tests/ -q` → 76 passed, 1 skipped(fastapi 미설치 로컬 한정).
- Blockers: 없음.
- Next: NEXT_PLAN 다음 [auto] — Tool Allowlist 정의 모듈(명령→허용 도구 매핑 + claude_runner 연결점).

## 2026-06-11 — sanitizer.py 구현 (주입 방어 1계층, overnight 회차)
- Status: 완료. Day 4–5 트랙 첫 항목 — wrap_untrusted + build_prompt.
- Changed: src/app/sanitizer.py(wrap_untrusted: 태그 위조 regex 무력화 — 대소문자/공백/속성 변형 포함,
  단일 패스 escape 로 재조합 불가; build_prompt: `{untrusted_data}` placeholder 강제 + template 내
  raw 태그 거부 + str.replace 로 이중 확장 방지, PromptTemplateError 신설).
  tests/test_sanitizer.py 16종(escape 변형/중첩/결합/placeholder 규약).
- Verified: `python3 -m pytest tests/ -q` → 62 passed, 1 skipped(fastapi 미설치 로컬 한정).
- Blockers: 없음.
- Next: NEXT_PLAN 다음 [auto] — claude_runner.py(subprocess 주입 mock, allowed_tools 전달).

## 2026-06-11 — overnight 자율 가동 러너 구축
- Status: 구축 완료. 실전 1회차(live) 검증은 사용자 직접 실행 대기.
- Changed: bin/overnight/run.sh(STOP/DONE/limit 30분 대기/연속실패 3회 중단/--once, 회차 간 30초),
  bin/overnight/PROMPT.md(회차 = sync → NEXT_PLAN [auto] 1개 → pytest green → checkpoint → commit),
  .claude/settings.json(allowlist + aws/push/curl/sudo deny, acceptEdits),
  NEXT_PLAN [auto]/[manual] 태깅 + 항목별 완료 기준, .gitignore(logs/STOP/DONE).
- Verified: bash -n / settings.json JSON 파싱 / STOP 파일 조기 종료(iterations=0) 통과.
  **live 1회차는 미검증** — 무인 에이전트 기동은 사용자 승인 필요로 차단됨.
- Blockers: 없음(검증만 잔여).
- Next: 사용자가 `bin/overnight/run.sh --once` 직접 실행 → 1회차 정상 확인 후
  `caffeinate -dimsu bin/overnight/run.sh &` 로 야간 가동.

## 2026-06-11 — Day 1–3 로컬 구현 (Socket Mode + ping + deploy 산출물)
- Status: 완료(로컬분). AWS/Slack 실행분은 ready-to-run 스크립트로 준비 — 자격증명 필요.
- Changed: slack_handler(Socket Mode lazy + 라우팅 + default deny 게이트), commands/ping 구현,
  job_queue(SQLite 원자 클레임), permissions(레벨 매핑 + 금지 불변), main(FastAPI health/metrics
  127.0.0.1 + Socket Mode 부트스트랩). deploy/ 신규: iam(RO policy/trust/create-role.sh),
  ec2(user-data.sh IMDSv2 + launch-instance.sh 인바운드 없는 SG), eventbridge(stop/start 스케줄),
  adot/collector-config.yaml, deploy/README.md. tests 4종 추가.
- Verified: `python3 -m pytest tests/ -q` → 46 passed, 1 skipped(fastapi 미설치 로컬 한정).
  bash -n / JSON 파싱으로 deploy 스크립트 문법 검증. e2e(/devops ping 실 Slack)는 미검증 — EC2 기동 필요.
- Blockers: 로컬 AWS 자격증명 무효(InvalidClientTokenId) → 프로비저닝 실행 불가. Slack App 생성은 수동 단계.
- Next: 운영자 수동 실행 — Slack App 생성 → SSM 토큰 저장 → create-role.sh → launch-instance.sh
  → create-schedules.sh → `/devops ping` e2e 확인. 이후 Day 4–5(Sanitizer + logs/diagnose).

## 2026-06-11 — repo bootstrap (harness + docs + src skeleton)
- Status: 완료. Day 1 빌드 착수 직전 스캐폴드 상태.
- Changed: BOOTSTRAP.md PART C(Step 1–8) 실행 — harness/CORE_MANDATES·CONTEXT_BRIDGE,
  docs current 8종, skill 3종(sync/checkpoint/tidy-docs), CLAUDE.md, src/app stub 골격,
  pyproject.toml / .env.example / .gitignore / tests smoke. 패키지명 slackops-devops-agent. git init.
- Verified: `python -m pytest tests/ -q` import smoke 통과(자세한 결과는 STATUS Baseline).
- Blockers: 없음.
- Next: Day 1–3 — EC2 + IAM Role + Claude Code + Socket Mode + `/devops ping`.

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
