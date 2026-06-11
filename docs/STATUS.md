# STATUS — slackops-devops-agent
최종 갱신: 2026-06-11

> 현재 상태/검증/risks (≤120줄). source of truth. 갱신은 /checkpoint.

## 현재 요약
- Day 1–3 **로컬 구현 완료**: Socket Mode 라우팅 + `/devops ping` + job queue + permission gate
  + FastAPI health/metrics. deploy/ 산출물(IAM/EC2/EventBridge/ADOT) ready-to-run.
- AWS/Slack **실행분 미수행**: 로컬 자격증명 무효 + Slack App 수동 생성 필요 → deploy/README.md 순서대로.

## 검증 Baseline
- `python3 -m pytest tests/ -q` → **62 passed, 1 skipped**(fastapi 미설치 로컬 한정 skip).
- lazy import 설계 — fastapi/slack_bolt 미설치 환경에서도 전 모듈 import-safe.
- `/devops ping` e2e 는 미검증(EC2 + Slack App 필요).

## 동작하는 것
- 명령 라우팅(default deny + 금지 불변 거부), ping 핸들러, SQLite job queue(원자 클레임),
  permission engine(L0/1 활성·L2 비활성), health/metrics(127.0.0.1 전용),
  sanitizer(wrap_untrusted 태그 위조 무력화 + build_prompt template 강제).
- stub 잔여: claude_runner / telemetry / commands(logs·diagnose·tf_review·pr).

## Active Focus
- 운영자 수동: deploy/README.md 1–4단계(Slack App → IAM → EC2 → EventBridge) → ping e2e.
- 다음 코드 트랙: Day 4–5 잔여 — claude_runner + Tool Allowlist + logs/diagnose.

## Open Risks
- untrusted input(CloudWatch 로그·git diff)이 곧 공격면 — Sanitizer/allowlist 우회 주의.
- IAM Instance Profile 외 자격증명 절대 금지(.env 는 example 만 커밋).
- EC2 상시 가동 시 비용 — EventBridge 스케줄 stop/start 확인.
- 비-목표(범위 밖): HTTPS 공개 엔드포인트, EC2 상시 가동, Level 2(Execute), Production/배포/IAM/DB 변경,
  SQLite 를 prod 데이터스토어로 호칭.
