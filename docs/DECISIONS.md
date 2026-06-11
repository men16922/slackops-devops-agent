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

## D5 — H0 해커톤 피벗: DynamoDB 이중 컨트롤플레인 (Vercel + Slack), B2B 트랙
- Decision: H0 해커톤(마감 2026-06-30) 제출을 위해 "One Agent, Two Control Planes"로 확장.
  job queue 를 SQLite → **DynamoDB 단일테이블**(jobs·audit·telemetry)로 승격, 사무실용 **Vercel/Next.js
  대시보드**(server actions↔DynamoDB) + 원격용 Slack 을 같은 DynamoDB 큐로 통합. 명령은 동기 호출에서
  **비동기 job 모델**로 전환. Track 2(B2B) 제출.
- Reason: 해커톤 통과 게이트(Vercel 프론트 + AWS DB + 풀스택)를 충족하면서 기존 백엔드(권한·주입방어·
  claude_runner·allowlist·telemetry)를 재사용. 두 인터페이스 공유 상태는 단일 writer SQLite 로 불가 →
  DynamoDB 가 설계상 필연. 한 번 빌드로 해커톤+AWSKRUG 발표+PACE+아티클을 커버.
- Impact: SQLite 는 로컬테스트 구현으로 강등(JobStore 프로토콜 뒤). 인바운드 금지 불변은 Slack 경로 유지,
  Vercel 은 아웃바운드 AWS SDK 별도 surface. 새 의존성 boto3(런타임)/moto(테스트). 계획: docs/plans/
  2026-06-12-h0-hackathon.md, 브랜치 hackathon-h0.
