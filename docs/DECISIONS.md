# DECISIONS — slackops-devops-agent
최종 갱신: 2026-06-11

> 되돌리기 어려운 결정만. 형식: Decision / Reason / Impact. 갱신은 /checkpoint.

## D1 — Slack 연결은 Socket Mode 전용
- Decision: 인바운드 HTTP 엔드포인트/공개 HTTPS/ALB/인증서 없이 Bolt Socket Mode 만 사용.
- Reason: 공격면 축소 + 인프라 단순화. 인바운드 포트 불필요.
- Impact: 공개 webhook 기반 기능 불가. EC2 아웃바운드만으로 동작.

## D2 — Job queue 는 SQLite (MVP 한정)
- Decision: MVP job queue 는 SQLite. prod 데이터스토어로 호칭/사용 금지.
- Reason: MVP 단순성. 운영 규모 데이터스토어는 범위 밖.
- Impact: 확장 시 교체 필요. 문서에서 "prod store" 표현 금지.

## D3 — 자격증명은 IAM Instance Profile 전용
- Decision: Access Key 저장/커밋 절대 금지. EC2 Instance Profile 만.
- Reason: 최소 권한 + 키 유출 방지(차별화 보안 축).
- Impact: 로컬/CI 실행 시 별도 자격증명 경로 필요. .env 는 example 만 커밋.

## D4 — 패키지/프로젝트명 = slackops-devops-agent
- Decision: pyproject `name` 및 식별자는 `slackops-devops-agent`(폴더명 SlackOps 반영).
- Reason: 현재 작업 폴더명과 정합. BOOTSTRAP 제안값 slack-devops-agent 대신 채택.
- Impact: 코드/설정 식별자 일관. 문서 본문 표기도 이 이름 기준.
