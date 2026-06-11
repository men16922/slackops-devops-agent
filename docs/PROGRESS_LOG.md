# PROGRESS_LOG — slackops-devops-agent
최종 갱신: 2026-06-11

> 최신 3–5개 증분 (≤120줄, 최신이 위). 넘치면 bin/docs/archive/progress-YYYY-MM.md 분리. append 는 /checkpoint.

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
