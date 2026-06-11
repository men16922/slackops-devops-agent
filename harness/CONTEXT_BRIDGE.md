# CONTEXT_BRIDGE — slackops-devops-agent
최종 갱신: 2026-06-11

> 초압축 핸드오프. source of truth 는 docs/STATUS.md·NEXT_PLAN.md, 이 파일은 압축본.

## Active Context
- 한 줄: Slack(Socket Mode) → EC2 Claude Code Headless 가 AWS/K8s/TF/GitHub 분석하는 DevOps agent. MVP=RO 분석+PR.
- 주 경로: src/app/ (slack_handler, permissions, sanitizer, claude_runner, telemetry, commands/).
- 차별화 축: 보안(권한 L0/1/2 + 주입 방어 4계층) + 계측(OTel).
- 문서 진입점: docs/AGENT_BRIEF.md → STATUS.md → NEXT_PLAN.md.

## Current Handover
1. Day 1–3: EC2 + IAM Role + Claude Code + Socket Mode + `/devops ping`.
2. 다음: logs/diagnose + Context Sanitizer.

## Open Risks
- untrusted input(로그·diff)이 곧 공격면 — Sanitizer/allowlist 우회 주의.
- IAM Instance Profile 외 자격증명 절대 금지.
- EC2 상시 가동 시 비용 — EventBridge 스케줄 확인.
