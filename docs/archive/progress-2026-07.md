# Progress archive — 2026-07

> Historical entries moved from `docs/PROGRESS_LOG.md` on 2026-07-15 and 2026-07-16. Current state lives in the active log.

## 2026-07-15 — P3 managed AWS MCP pilot guardrail scaffold
- Status: Done for the local/CI scaffold; no AWS resources or EC2/live rehearsal performed.
- Changed: added a separate-account pilot contract, a context-key-bound three-action CloudWatch Logs read policy, mutation deny,
  CloudTrail Lake violation-query template, operator runbook, and isolation regression tests.
- Verified: dedicated P3 tests, `make check`, and `git diff --check` pass; runtime deploy files do not reference the pilot role
  or `aws-mcp.amazonaws.com`.
- Blockers: Manual pilot still needs distinct real account IDs, a reviewed trust policy, one approved read event, and an empty
  CloudTrail violation query. VPC endpoint support is not assumed.
- Next: commit P2 + dashboard seed + P3 bundle; manual Slack approver validation and slide design remain independent.

## 2026-07-15 — Dashboard seed rationale English cleanup
- Status: Done; no EC2/live rehearsal performed.
- Changed: translated `agent-2001` and `agent-2002` Proposal rationale strings in the DynamoDB Local seed.
- Verified: static seed parsing/build checks; no Korean remains in either agent rationale.
- Blockers: None. This affects local demo seed data only, not production records.
- Next: commit pending P2 + seed cleanup; finish slide design and manual Slack approver verification when desired.

## 2026-07-15 — P2 deterministic command scope boundary
- Status: Done; final fresh-EC2 rehearsal stopped and private source artifact bucket removed.
- Changed: fixed account/region/resource/time scopes before adapters/executors and again before Claude; root-owned EC2 policy env, 24-hour log lookback, Worker scope-denial audit with reason/context.
- Verified: `make check` 408 passed; all commands have tested fixed scopes; fresh EC2 denied an unreviewed log group before fetch and wrote Worker `policy_denied` evidence.
- Blockers: None. P2 is local/ahead of remote until commit/push; managed MCP expansion remains a separate environment.
- Next: commit/push D16–D17/P1/P2 bundle; finish slides/live-demo rehearsal, then P3 organization pilot if needed.

## 2026-07-15 — P1 central system-boundary audit sink
- Status: Done; final fresh-EC2 rehearsal stopped and private source artifact bucket removed.
- Changed: deployment-provisioned 30-day CloudWatch audit group; root-only audit STS role, root-only credential/env/state paths, exporter/timer for credential rotation and URL-free Squid deny events; runtime role has an explicit deny for this sink.
- Verified: fresh cloud-init + 4 agent services/2 timers active; audit env `600` and state `700` root-owned/unreadable by agent; runtime `PutLogEvents` explicit deny; CloudWatch contains `credential_refresh` and `proxy_denied` (`squid_status` only).
- Blockers: None. Source changes remain local/ahead of remote; do not describe this as remote-main production deployment until push.
- Next: commit/push D16–D17/P1 bundle; P2 deterministic policy interceptor, then slide/live-demo rehearsal.

## 2026-07-15 — D17 fresh-EC2 runtime boundary rehearsal
- Status: Done; final rehearsal EC2 stopped and temporary encrypted source artifact bucket removed.
- Changed: MCP proposal/policy/approval/plan-binding audit events; hash-verified pre-push source archive path; fixed Squid redundant Terraform ACL and DynamoDB runtime/MCP policy region ARN; added Squid ACL regression test.
- Verified: fresh EC2 source archive + 4 services/timer active; runtime/MCP STS identities and forced rotation; fixed AWS read; IMDS/direct-egress deny; GitHub proxy allow/unlisted HTTPS deny; MCP `ping` audit `proposed→claimed→done`.
- Blockers: None. Source changes are local/ahead of remote; do not describe D16/D17 as remote-main deployed until push.
- Next: commit/push this bundle; P1 central agent-unwritable audit sink for credential-refresh and proxy-deny evidence.

## 2026-07-15 — D15 보안 런타임: GitHub 인증 + 불변 PR 실행계획
- Status: Production deployed; review/commit remains.
- Changed: dashboard GitHub OAuth/allowlist, Slack approver allowlist, canonical execution-plan/approval hash, workspace·tool-chain·remote-PR-diff verification, append-only audit hash chain, EC2 systemd hardening; `make vercel-deploy` syncs the four OAuth values from root `.env`.
- Verified: `make check` (367 passed, Ruff, mypy, doc budget), `cd web && npm run build`, `git diff --check`, Docker dashboard build/seed + API smoke; Vercel Production build READY, `/`→`/login` 307, login page 200, real GitHub login succeeded.
- Blockers: `SLACK_APPROVER_IDS` is synced to SSM; only the interactive Slack approval-button proof remains.
- Next: commit this scoped bundle, then AWSKRUG slide/rehearsal. Details: `docs/reports/2026-07-15-secure-runtime-report.md`.

## 2026-07-10 — web 대시보드 리디자인 (AWS/Datadog 스타일 라이트 테마 + 관측성 컴포넌트)
- Status: Done. 다크(GitHub풍) → AWS 콘솔/Datadog 감성 라이트 테마 전면 리디자인. 커밋 `35f4b38` (feature/dashboard-aws-theme, 7 files, +613/-148).
- Changed: `web/app/globals.css` 대폭(토큰 팔레트 재정의 + 컴포넌트) — 딥네이비 nav(+2px 오렌지 스파크)/화이트·cool-gray 본문/블루·오렌지 포인트.
  KPI 스탯 타일(상단 컬러 스트라이프+tone+tabular 대형숫자), STATUS(캡슐 pill+둥근 dot)↔SOURCE(플랫 라벨+네모 스와치) 형태 분리,
  테이블 헤더 틴트+제브라+숫자 우측정렬/tabular. `Chat.tsx`=ops 콘솔 카드(블루 그라데이션+아이콘 배지+헤더+예시 칩).
  `page.tsx` ARGS→Proposal 컬럼(pr=변경내용/그외=rationale, 없으면 —, 한줄 말줄임+title) + 상단 KPI 밴드 + LIVE 인디케이터.
  이모지 제거(source/chat 역할/제안), `NotificationBell.tsx` 벨 SVG 아이콘화, `layout.tsx` nav 연결칩(DynamoDB)+본문폭 1080→1440 정렬.
- Verified: `docker compose up --build`(로컬 스택 8930) 반복 재빌드 = `next build` green. Playwright로 Jobs/Metrics/상세/Detections 4화면 실렌더 확인(1440·1728 뷰포트).
- Blockers: 시드 mock rationale 2개(agent-2001/2002)가 한글 — Proposal 컬럼 노출로 DOM에 한글 등장(H0 English UI 위배 소지). 번역 미결(사용자 판단 대기).
- Next: (선택) main 머지 / 시드 rationale 영어화 / nav 벨 외 잔여 확인.

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
