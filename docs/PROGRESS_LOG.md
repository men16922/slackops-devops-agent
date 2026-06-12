# PROGRESS_LOG — slackops-devops-agent
최종 갱신: 2026-06-12

> 최신 3–5개 증분 (≤120줄, 최신이 위). 넘치면 bin/docs/archive/progress-YYYY-MM.md 분리. append 는 /checkpoint.

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
