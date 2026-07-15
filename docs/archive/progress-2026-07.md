# Progress archive — 2026-07

> Historical entries moved from `docs/PROGRESS_LOG.md` on 2026-07-15. Current state lives in the active log.

## 2026-07-06 — slides v2 and healthz

- AWSKRUG 13-page slide deck and presentation script updated; `/healthz` added and tested (`make check` 359 passed).

## 2026-07-06 — D4 real AWS e2e

- EC2 CloudWatch diagnosis and MCP write-denied behavior verified, then instance stopped. This was the pre-D16 generic AWS MCP path.

## 2026-07-05 — workspace and presentation cleanup

- Retired Devpost artifacts, archived completed plans, reduced local workspace, and prepared AWSKRUG presentation materials.

## 2026-07-04 — overnight harness plugin migration

- Moved the harness runner to plugin-based resolution and added the Kiro engine configuration.

## 2026-07-02 — real Slack sandbox e2e

- Verified DM fallback, streaming diagnosis, approval action/audit, Canvas creation, and telemetry footer in the real Slack workspace.

## 2026-07-02 — local assistant mock fallback

- Added offline and real console paths for diagnosis, PR approval flow, Canvas output, and prompt-injection rejection evidence.

## 2026-07-01 — v2 QA and dashboard verification

- Reframed QA around local Docker, real Slack, real AWS, and human checks; verified dashboard feed, approval transition, and metrics rendering.

## 2026-06-27 — Assistant flow verification

- Extracted the testable Assistant core and verified diagnosis/Canvas and PR approval end-to-end without a Slack binding.

## 2026-06-26 — AWSKRUG pivot

- Retired the ineligible Devpost goal and adopted the Slack Assistant + human approval + Canvas live-demo direction.
