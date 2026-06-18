# CONTEXT_BRIDGE — slackops-devops-agent
Last updated: 2026-06-12

> Ultra-compressed handoff. Source of truth is docs/STATUS.md·NEXT_PLAN.md; this file is the compressed version.

## Active Context
- One line: DevOps agent where Slack (Socket Mode) → EC2 Claude Code Headless analyzes AWS/K8s/TF/GitHub. MVP=RO analysis+PR.
- Main path: src/app/ (slack_handler, permissions, sanitizer, claude_runner, telemetry, commands/).
- Differentiators: security (permission L0/1/2 + 4-layer injection defense) + instrumentation (OTel).
- Doc entry point: docs/AGENT_BRIEF.md → STATUS.md → NEXT_PLAN.md.

## Current Handover
1. Day 1–5 local part complete (routing/ping/permissions/sanitizer/claude_runner/allowlist/logs/diagnose).
   Remaining = AWS/Slack manual execution (deploy/README.md) + H0 [manual] (credits / DynamoDB provision / v0 dashboard).
2. H0 store/ + telemetry + worker + commands **complete**: JobStore/AuditStore/TelemetryStore
   (single table) + record_run_metrics + Worker polling loop (output gate/write-back) +
   tf-review (isolated plan review, no apply) + pr (2-stage gate — prepare strips push/PR tool
   argv + extracts diff, execute only after approval; pr goes through worker only) — pytest 216 passed.
   Next [auto] = Day 8–9 Observability (real setup_telemetry implementation + instrumentation wiring).

## Open Risks
- Untrusted input (logs/diffs) is itself an attack surface — watch for Sanitizer/allowlist bypass.
- Never use credentials other than the IAM Instance Profile.
- Cost if EC2 runs always-on — verify the EventBridge schedule.
