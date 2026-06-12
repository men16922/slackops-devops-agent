# STATUS — slackops-devops-agent
최종 갱신: 2026-06-12

> 현재 상태/검증/risks (≤120줄). source of truth. 갱신은 /checkpoint.

## 현재 요약
- Day 1–3 **로컬 구현 완료**: Socket Mode 라우팅 + `/devops ping` + job queue + permission gate
  + FastAPI health/metrics. deploy/ 산출물(IAM/EC2/EventBridge/ADOT) ready-to-run.
- AWS/Slack **실행분 미수행**: 로컬 자격증명 무효 + Slack App 수동 생성 필요 → deploy/README.md 순서대로.

## 검증 Baseline
- `python3 -m pytest tests/ -q` → **216 passed, 1 skipped**(fastapi 미설치 로컬 한정 skip).
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
- stub 잔여: telemetry OTel 파이프라인(setup_telemetry).

## Active Focus
- [auto] 잔여: Day 8–9 Observability — setup_telemetry 실 구현 + claude_runner/commands 계측 결합.
- 운영자 수동: v0 대시보드 + AWS/v0 크레딧 + DynamoDB provision + deploy/README.md 1–4단계 → ping e2e.

## Open Risks
- untrusted input(CloudWatch 로그·git diff)이 곧 공격면 — Sanitizer/allowlist 우회 주의.
- IAM Instance Profile 외 자격증명 절대 금지(.env 는 example 만 커밋).
- EC2 상시 가동 시 비용 — EventBridge 스케줄 stop/start 확인.
- 비-목표(범위 밖): HTTPS 공개 엔드포인트, EC2 상시 가동, Level 2(Execute), Production/배포/IAM/DB 변경,
  SQLite 를 prod 데이터스토어로 호칭.
