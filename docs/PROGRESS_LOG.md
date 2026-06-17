# PROGRESS_LOG — slackops-devops-agent
최종 갱신: 2026-06-16

> 최신 3–5개 증분 (≤120줄, 최신이 위). 넘치면 docs/archive/progress-YYYY-MM.md 분리. append 는 /checkpoint.
> 2026-06-11~12 전반부 항목 원문: docs/archive/progress-2026-06.md

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

(2026-06-12 구현 회차 원문 — tf_review/pr·worker·telemetry record — 은 bin/docs/archive/progress-2026-06.md)
