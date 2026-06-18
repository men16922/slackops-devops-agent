# PROGRESS_LOG — slackops-devops-agent
최종 갱신: 2026-06-19

> 최신 3–5개 증분 (≤120줄, 최신이 위). 넘치면 docs/archive/progress-YYYY-MM.md 분리. append 는 /checkpoint.
> 2026-06-11~12 전반부 항목 원문: docs/archive/progress-2026-06.md

## 2026-06-19 — 대화형 producer: web 채팅 → 에이전트 스트리밍 → propose_job (DECISIONS D10)
- Status: 완료. selectbox producer 를 자연어 채팅으로 대체 — 실 Claude e2e 검증까지.
- Changed: **store/chat_store.py**(신규) 대화 버스(Conversation/Message/ChatStatus + Sqlite/DynamoDb,
  단일테이블 PK=CHAT#/META, **GSI1 CHATSTATUS# 오버로딩으로 claim — 새 GSI 0**, 청크 list_append).
  **claude_runner.run_headless_stream**(신규) stream-json 줄파싱 → on_chunk 콜백 + tokens/cost +
  propose_job job_id 추출. **chat_agent.py**(신규) 폴링 consumer(claim→sanitizer 격리→스트리밍→
  finish, allowedTools=propose_job only). **web/**: Chat.tsx(폴링 Markdown 렌더)+chat-actions.ts+
  api/chat/[conv] 라우트, Markdown.tsx 공유 이전, NewCommand 삭제. mcp_config_json 에 AWS 더미키
  passthrough(로컬 실 Claude). make chat-agent. USER_GUIDE §2.4-2.5/런북 갱신.
- Verified: `make check` green(**270 passed, 1 skipped** · ruff · mypy 27 files) + web `next build` TS strict +
  Playwright e2e(입력→DynamoDB→chat_agent(mock+**실 Claude**)→폴링 Markdown 렌더+제안 콜아웃→Job Queue).
  실 Claude: checkout 504 멀티턴 진단 + propose_job 실제 job 적재 확인. 증빙 docs/images/chat-producer-e2e.png.
- Blockers: 없음. (page reload 시 채팅 state 초기화 — convId 미영속, 데모 한정.)
- Next: H0 [manual] — AWS provision/배포/제출. (선택: reload localStorage 영속, Vercel SSE 브리지.)

## 2026-06-18 — 세션 묶음: Quarkify 포팅 + worker 로컬 엔트리 + web Markdown/정렬 + GUIDE 통합/QA
- Status: 완료. H0 로컬 데모 품질·검증 정비(별도 [manual] AWS 트랙 무변).
- Changed: Quarkify 코드 토폴로지 인덱스 포팅(tools/quarkify + 비차단 freshness + 정책문서, 실측 앵커).
  worker 로컬 CLI 엔트리(`python -m app.worker`, stores_from_env) → 풀 루프 로컬 완결. Makefile
  DEV_ENV(PYTHONPATH=src + DDB 더미키) — agent-monitor/worker/chat-agent. web 작업결과 Markdown
  렌더(Markdown.tsx, 중첩 emphasis)+agent source 정렬. END_USER_GUIDE→USER_GUIDE 병합, QA_LIST.md 신설.
- Verified: `make check` green(250→262 passed 경유) + Playwright 로 §3-A 대시보드 클릭 UX 전수(승인 전이/
  낙관적 락/Telemetry/producer) + 실 Claude diagnose 풀 루프($0.25/4838tok). 증빙 docs/images/.
- Blockers: 없음.
- Next: 대화형 producer(위 2026-06-19) → H0 [manual] 제출 트랙.

## 2026-06-17 — 에이전트 자율 제안 루프(MCP propose_job) + 사람 web producer (DECISIONS D9)
- Status: 완료. control plane 을 에이전트까지 확장 — "감지→제안→사람 승인" 루프 구현(로컬 e2e).
- Changed: **src/app/mcp_server.py**(신규) propose_job/list_pending(FastMCP, server=slackops, 순수
  로직/SDK 래퍼 분리, permissions default-deny 재사용). **src/app/agent_monitor.py**(신규) Tier1
  시뮬레이터(detect 규칙기반·토큰불필요)+Tier2 실제 run_monitor_headless(--mcp-config). store/
  (base/dynamodb/sqlite) 에 `JobSource.AGENT`+`Job.rationale` 전용 필드(extra 미영속이라 필수).
  claude_runner.build_command(mcp_config)→--mcp-config+--strict-mcp-config. **web/**: 사람 producer
  (NewCommand 채팅/selectbox + actions.enqueueJob) + agent 뱃지·rationale 콜아웃, seed 에이전트
  샘플 2건, docker-compose dynamodb-local 8931 노출. pyproject mcp>=1.0(+mypy override). Makefile
  mcp-server/agent-monitor. END_USER_GUIDE.md, docs/runbooks/agent-mcp-demo.md. 커밋 f1caa80.
- Verified: `make check` green(**249 passed, 1 skipped** · ruff · mypy strict) + web `tsc` green +
  docker e2e(seed 28건, 홈/상세 agent 렌더 — 🤖 뱃지/rationale/diff/Approve) + Tier1 라이브
  (agent_monitor 시뮬레이터→DynamoDB Local 8931→FEED agent 제안 3건 확인).
- Blockers: 없음. (Tier2 실제 claude -p 는 OAuth 토큰 필요 → env 미설정, 런북 문서화·미실행.)
- Next: H0 [manual] — DynamoDB provision/Vercel 배포/제출물. (로컬 데모는 worker 미가동→제안 pending 정지.)

## 2026-06-17 — overnight-harness 플러그인 수렴 (리포 로컬 하네스 중복 제거)
- Status: 완료. 자작 플러그인을 단일 소스로 — 스킬/러너/엔지니어링 문서 3계층 중복 제거(DECISIONS D8).
- Changed: harness-init 스캐폴드(scripts/overnight/* + docs/engineering/* bibles + .claude/harness-config.json
  + docs/test/bible + Makefile snippet). 리포 로컬 스킬 4종 삭제(.claude/skills/{sync,checkpoint,tidy-docs,
  overnight-report}) → 플러그인 사용. 러너 bin/overnight → scripts/overnight 이전(PROMPT 에 리포 불변
  CORE_MANDATES/aws→mock/lazy import/CONTEXT_BRIDGE read path/한국어 포팅, overnight-settings 에 aws deny 보강).
  docs/LOOP_ENGINEERING.md → docs/engineering/interp/INTERPRETATION.md 흡수 후 삭제. Makefile 신규
  (check=pytest+ruff+mypy + overnight 타깃). 아카이브 bin/docs/archive → docs/archive 이전.
  CLAUDE.md/DOCS_POLICY/README/.gitignore 참조 갱신. (보존: harness/ mandates, docs 상태문서, 인터랙티브 settings.)
- Verified: `make check` green(229 passed, 1 skipped · ruff · mypy). 구조 검증(중복 스킬 0, bin 제거,
  활성 문서 bin 참조 0, run.sh/status.sh 문법 OK). 라이브 overnight-once 스모크는 커밋 후 진행.
- Blockers: 없음. (스킬 bare 호출명 `/sync` 해석은 실사용 확인 예정.)
- Next: H0 [manual] — DynamoDB provision/Vercel 배포/제출물.

## 2026-06-16 — web/ 대시보드(Next.js, 로컬 Docker) + USER_GUIDE.md + Claude 구독 추론 결정
- Status: 완료. H0 핵심 스택(Vercel 프론트 + DynamoDB)의 프론트 첫 구현 — 로컬 e2e 검증까지.
- Changed: **web/** 신규 — Next.js 14.2.35 App Router(TS). lib/{types,time,ddb,format}.ts
  (단일테이블 계약 TS 미러 — GSI2 FEED/AUDIT/METRIC 질의, _util.py utcnow_iso/day_of 동형),
  app/{page(jobs feed),jobs/[id](상세+diff 출력게이트+Approve/Reject+audit),metrics},
  actions.ts(승인 server action = _conditional_set ConditionExpression + audit append 미러),
  scripts/seed.mjs(create-table.sh 스키마로 테이블 생성 + mock 22건). docker-compose(dynamodb-local
  오프라인 + seed + web, **포트 8930**, 더미 키 — 실 AWS 불필요), Dockerfile, .env.local.example.
  **USER_GUIDE.md**(루트) — 시크릿 수동 입력 가이드(Slack/Claude→SSM, AWS 키는 Vercel/실DynamoDB
  읽을 때만 최소권한 IAM, 발급·정책·회전·심사기간 비용절약). deploy/{ec2/user-data.sh,README.md}
  에 CLAUDE_CODE_OAUTH_TOKEN(SSM) 로드 추가. .gitignore web/ 항목.
- Verified: `next build` green(TS strict) + **docker compose up e2e**: seed 22건, web 8930 응답,
  jobs/상세/metrics 렌더 + **승인 전이 동작·중복승인 ConditionalCheckFailed 거부**(낙관적 락) 확인.
  게이트 3계층: pytest 229 passed/1 skipped · ruff green · mypy green(src 무변경).
- Blockers: 없음. (잔여 postcss moderate/high 취약점은 Next 16 메이저 필요 — 보류.)
- Next: [manual] — DynamoDB provision → EC2 e2e 캡처 → Vercel 배포(실 DynamoDB, 읽기키 env) → 제출물.
