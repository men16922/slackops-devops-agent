# AGENT_BRIEF — slackops-devops-agent
최종 갱신: 2026-06-11

> 1분 압축 진입점 (≤60줄). 표준은 harness/CORE_MANDATES.md, 작업 권위는 NEXT_PLAN.md > docs/plans/.

## Read Path (세션 시작/재개)
harness/CONTEXT_BRIDGE.md → docs/AGENT_BRIEF.md → docs/STATUS.md → docs/NEXT_PLAN.md
→ (필요 시) docs/PROGRESS_LOG.md 상단 → (필요 시) bin/docs/archive/

## Snapshot
- **무엇:** Slack 자연어 명령 → EC2 의 Claude Code Headless 가 AWS/K8s/Terraform/GitHub 컨텍스트 분석 → 운영 자동화.
  MVP = Read-Only 분석 + PR 생성까지.
- **차별화:** 단순 봇이 아니라 "에이전트를 안전하게 운영하는 법"의 레퍼런스 — 보안(권한 + 주입 방어) + 계측(OTel).
- **동작:** 명령 라우팅 + ping + job queue + permission gate + sanitizer + claude_runner
  + allowlist(run_for_command 단일 진입점) + logs/diagnose 핸들러(fetcher 주입→격리→조립,
  diagnose 는 다중 소스+소스별 실패 격리) — 로컬 검증. AWS/Slack 실행분은 deploy/ 준비 완료.
- **검증:** `python3 -m pytest tests/ -q` → 120 passed, 1 skipped.
- **현재 초점:** Day 1–3 잔여(운영자 수동, deploy/README.md) + Day 4–5 잔여(logs/diagnose 라우팅 등록).

## Guardrails 요약 (상세는 CORE_MANDATES)
- Socket Mode 전용(인바운드 포트 금지). IAM Instance Profile 만(Access Key 금지).
- 권한 L0/1 만 활성, L2(Execute) 비활성. Production/배포/IAM/DB 변경 금지.
- 주입 방어 4계층: Sanitizer / Tool Allowlist / 출력 게이트 / Template Prompt.
- EC2 는 EventBridge 스케줄 가동(상시 금지).

## Slack 명령 (MVP)
- `/devops ping` — 헬스체크
- `/devops logs <service>` — CloudWatch 조회 + 분석
- `/devops diagnose <service>` — CloudWatch + kubectl + git diff 종합 진단
- `/devops tf-review` — terraform plan 위험/비용/보안 리뷰
- `/devops pr <설명>` — branch → 수정 → test → PR (사람 확인 게이트)

## 슬래시 커맨드 (작업 하네스)
- `/sync` — 세션 시작/재개 시 Read Path 만 읽고 요약 (읽기만)
- `/checkpoint` — 작업 묶음 완료 시 PROGRESS_LOG append + 조건부 갱신 (기록만)
- `/tidy-docs` — 문서 비대 시 archive 분리·압축·통합 (정리만)
