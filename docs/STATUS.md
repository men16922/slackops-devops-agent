# STATUS — slackops-devops-agent
최종 갱신: 2026-06-19

> 현재 상태/검증/risks (≤120줄). source of truth. 갱신은 /checkpoint.

## 현재 요약
- Day 1–3 **로컬 구현 완료**: Socket Mode 라우팅 + `/devops ping` + job queue + permission gate
  + FastAPI health/metrics. deploy/ 산출물(IAM/EC2/EventBridge/ADOT) ready-to-run.
- AWS/Slack **실행분 미수행**: 로컬 자격증명 무효 + Slack App 수동 생성 필요 → deploy/README.md 순서대로.

## 검증 Baseline
- 게이트 3계층: `python3 -m pytest tests/ -q` → **274 passed, 1 skipped**(fastapi 미설치 로컬 한정 skip)
  + `ruff check src tests` + `mypy src`(strict) 전부 green.
- web/: `next build` green(TS strict) + `docker compose up` e2e — seed 22건, 8930 응답, jobs/상세/metrics
  렌더 + 승인 전이·중복승인 ConditionalCheckFailed 거부 확인(2026-06-16).
- lazy import 설계 — fastapi/slack_bolt 미설치 환경에서도 전 모듈 import-safe.
- code-review(high) 후속 10 findings 수정 완료 — route 예외 안전망, sanitizer 미완성태그,
  kubectl 플래그 주입, CloudWatch 최신 이벤트, run.sh limit 판정, 명령 레지스트리 단일화 등.
- `/devops ping` e2e 는 미검증(EC2 + Slack App 필요).

## 동작하는 것
- 명령 라우팅(default deny + 금지 불변 거부), ping 핸들러, SQLite job queue(원자 클레임),
  permission engine(L0/1 활성·L2 비활성), health/metrics(127.0.0.1 전용),
  sanitizer(wrap_untrusted 태그 위조 무력화 + build_prompt template 강제),
  claude_runner(run_headless — 실행기 주입, allowedTools 전달, JSON→RunResult 파싱, timeout),
  allowlist(명령별 Tool Allowlist 매핑 + run_for_command 단일 진입점 — permissions 게이트 →
  allowlist → run_headless, 금지 키워드 import-time 검증, default deny),
  commands/logs(handle_logs — fetcher 주입→sanitizer 격리→run_for_command 조립,
  service 인자 regex 검증, boto3 lazy 기본 fetcher),
  commands/diagnose(handle_diagnose — 다중 소스 fetchers 주입(logs/kubectl/git diff),
  소스별 실패 격리, 섹션 마커 단일 격리 블록, 전 소스 빈 데이터 시 Claude 미호출),
  라우팅 등록(register_default_commands — ping/logs/diagnose, 호출 시점 모듈 속성 조회),
  store/(H0 단일테이블 — JobStore 상태머신+claim 원자성, AuditStore append/job·일자 피드,
  TelemetryStore record/피드 — 각각 Sqlite+DynamoDb 양 구현, moto 동치 검증),
  telemetry(record_run_metrics — 주입된 TelemetryStore 에 기록, setup_telemetry 는 OTel lazy stub),
  worker(Worker.process_one — claim→executor→diff 미승인이면 await_approval 출력게이트,
  아니면 DONE/예외 FAILED + audit/metric write-back, run_forever 주입 sleep 폴링,
  default_executors ping/logs/diagnose/tf-review/pr, 매핑 외 명령 default deny),
  commands/tf_review(handle_tf_review — PlanFetcher 주입(기본 argv `terraform plan` 고정,
  apply 경로 부재 테스트), plan 격리 → 위험/비용/보안 리뷰),
  commands/pr(handle_pr 2단계 — prepare 는 push/PR 도구를 argv 에서 제거(exclude_tools,
  좁히기 전용)하고 마커로 diff 추출 → PrResult.diff → worker 게이트, execute(승인 후)만
  전체 allowlist 로 push+`gh pr create`; 설명은 길이 검증 후 격리 블록으로만 전달),
  slack 동기 경로에 tf-review 등록(pr 은 게이트가 store 상태를 요구해 worker 경유 전용).
- telemetry(setup_telemetry 실 구현 — TracerProvider+SimpleSpanProcessor, exporter 주입/OTLP lazy,
  미설치 None; record_run_metrics tracer 주입 시 devops.run span emit, store 기록 불변),
  계측 결합(run_for_command on_metrics — 모든 Claude 호출 단일 진입점 계측, 핸들러 4종
  passthrough, worker 가 실 tokens/cost 를 CommandOutcome/metric/job 에 write-back,
  Worker tracer 주입 시 OTel span emit). stub 잔여 없음.
- **web/ 대시보드(Next.js 14.2.35 App Router, TS)** — 로컬 e2e 검증 완료. lib/ddb(단일테이블 계약
  TS 미러: GSI2 FEED/AUDIT/METRIC 질의), app/{jobs feed, 상세=diff 출력게이트+Approve/Reject+audit,
  metrics 집계}, actions(승인 server action = ConditionExpression 전이+audit append, 낙관적 락),
  scripts/seed.mjs(create-table.sh 스키마 + mock 22건). docker-compose(dynamodb-local 오프라인+seed+web,
  포트 8930, 더미 키=실 AWS 불필요). DDB_ENDPOINT 토글로 로컬↔실 DynamoDB 전환(D7).
- 운영 배포 준비: user-data.sh/deploy README 에 Claude 구독 OAuth 토큰(SSM) 로드 추가(D6).
  USER_GUIDE.md(루트) — 운영자 시크릿 수동 입력 가이드.
- **에이전트 자율 제안 루프(D9)** — control plane 을 사람+에이전트 공유 producer 로 확장.
  mcp_server(propose_job/list_pending — FastMCP server=slackops, 순수로직/래퍼 분리, permissions
  default-deny 재사용), agent_monitor(Tier1 시뮬레이터 detect 규칙 + Tier2 실제 claude -p
  --mcp-config), claude_runner.build_command(mcp_config). 기존 출력 게이트 재사용(신규 store 상태
  없음): 제안=PENDING/source=agent, L1 은 await_approval 로 사람 승인 대기. store 에 JobSource.AGENT
  +Job.rationale 추가. web/ 에 사람 producer(NewCommand 채팅/selectbox+enqueueJob) + agent 뱃지·
  rationale 표시, seed 에이전트 샘플 2건, dynamodb-local 8931 노출. 런북 docs/runbooks/agent-mcp-demo.md.

- **대화형 producer(D10, 2026-06-19)** — selectbox 를 자연어 채팅으로 대체. DynamoDB 대화 버스
  (store/chat_store.py, GSI1 오버로딩) + claude_runner.run_headless_stream(stream-json) + chat_agent.py
  (폴링 consumer, sanitizer 격리, propose_job only) + web Chat.tsx(폴링 Markdown 렌더)+api/chat 라우트.
  에이전트 인바운드 0(폴링만)→Vercel 동작. **실 Claude e2e 검증**(checkout 504 진단+propose_job 적재).
  make chat-agent. (web 작업결과 Markdown 렌더 + Quarkify 포팅 + worker 로컬 엔트리도 본 세션.)

- **데모/품질 정비(2026-06-19 2차)**: `make demo`(scripts/demo.sh) 로컬 풀스택 한 방(web+DB+chat_agent+worker).
  대화형 producer orphan convId 잠금 fix(재시드 후 자가복구+재시도). 채팅/결과 pretty 렌더
  (Markdown 표·수평선·링크 + claude_runner ANSI strip). user-data.sh 에 worker·chat_agent systemd 상주
  (클라우드 풀 루프 갭 닫음). Playwright 실 Claude e2e 로 채팅 동작·표 렌더 검증.

## Active Focus
- 로컬 코드 완성(백엔드 [auto] + web/ 대시보드 + 대화형 producer + make demo 풀스택). 잔여는 전부 **[manual] AWS/배포/제출**.
- AWS 크레딧 신청 **거절** → 보유 $63.91 + 무료티어로 진행. 다음: DynamoDB provision →
  Vercel 배포(실 DynamoDB) → EC2 e2e 캡처 → 제출물. 심사기간(~7/24) EC2 stop(비용 ~$0).

## Open Risks
- untrusted input(CloudWatch 로그·git diff)이 곧 공격면 — Sanitizer/allowlist 우회 주의.
- IAM Instance Profile 외 자격증명 절대 금지(.env 는 example 만 커밋).
- EC2 상시 가동 시 비용 — EventBridge 스케줄 stop/start 확인.
- 비-목표(범위 밖): HTTPS 공개 엔드포인트, EC2 상시 가동, Level 2(Execute), Production/배포/IAM/DB 변경,
  SQLite 를 prod 데이터스토어로 호칭.
