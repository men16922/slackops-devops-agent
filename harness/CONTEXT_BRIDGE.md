# CONTEXT_BRIDGE — slackops-devops-agent
최종 갱신: 2026-06-12

> 초압축 핸드오프. source of truth 는 docs/STATUS.md·NEXT_PLAN.md, 이 파일은 압축본.

## Active Context
- 한 줄: Slack(Socket Mode) → EC2 Claude Code Headless 가 AWS/K8s/TF/GitHub 분석하는 DevOps agent. MVP=RO 분석+PR.
- 주 경로: src/app/ (slack_handler, permissions, sanitizer, claude_runner, telemetry, commands/).
- 차별화 축: 보안(권한 L0/1/2 + 주입 방어 4계층) + 계측(OTel).
- 문서 진입점: docs/AGENT_BRIEF.md → STATUS.md → NEXT_PLAN.md.

## Current Handover
1. Day 1–5 로컬분 완결(라우팅/ping/permissions/sanitizer/claude_runner/allowlist/logs/diagnose).
   잔여 = AWS/Slack 수동 실행(deploy/README.md) + H0 [manual](크레딧/DynamoDB provision/v0 대시보드).
2. H0 store/ + telemetry + worker + commands **완료**: JobStore/AuditStore/TelemetryStore
   (단일테이블) + record_run_metrics + Worker 폴링 루프(출력게이트/write-back) +
   tf-review(plan 격리 리뷰, apply 부재) + pr(2단계 게이트 — prepare 는 push/PR 도구
   argv 제거+diff 추출, execute 는 승인 후만; pr 은 worker 경유 전용) — pytest 216 passed.
   다음 [auto] = Day 8–9 Observability(setup_telemetry 실 구현 + 계측 결합).

## Open Risks
- untrusted input(로그·diff)이 곧 공격면 — Sanitizer/allowlist 우회 주의.
- IAM Instance Profile 외 자격증명 절대 금지.
- EC2 상시 가동 시 비용 — EventBridge 스케줄 확인.
