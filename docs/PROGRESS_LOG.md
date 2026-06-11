# PROGRESS_LOG — slackops-devops-agent
최종 갱신: 2026-06-12

> 최신 3–5개 증분 (≤120줄, 최신이 위). 넘치면 bin/docs/archive/progress-YYYY-MM.md 분리. append 는 /checkpoint.

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
