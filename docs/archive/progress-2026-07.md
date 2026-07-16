# Progress archive — 2026-07

> Historical entries moved from `docs/PROGRESS_LOG.md` on 2026-07-15 and 2026-07-16. Current state lives in the active log.

## 2026-07-16 — D20 capability taxonomy, risk aggregation, re-approval triggers (Notion P1)
- Status: Done for local/CI. No EC2/live rehearsal.
- Found first: `capabilities_for_tools` classified by substring, so `git add`, `git checkout`,
  `python -m pytest`, `terraform plan` and `terraform show` all aggregated to **no capability at all** —
  a tool chain's cumulative risk read lower than it was, which is exactly the multi-tool composition case.
- Changed: replaced the heuristic with a declared 5-class taxonomy (read/sensitive-read/write-low/write-high/
  privileged); an unclassified tool or capability now fails closed instead of scoring 0. Added per-capability
  risk summed across the whole chain, with `RISK_CEILING = 10` — write-high (20) and privileged (50) exceed it
  alone, so "L2 disabled" and "privileged blocked" are one arithmetic rule, not a special-case list. `risk_score`,
  `risk_ceiling`, `account_id` and `region` are now pinned in the hashed plan; verification re-scores rather than
  trusting the stored number and holds the plan to the ceiling **in force at approval**, so a later policy cannot
  retroactively bless it. Over-ceiling plans are refused at build time (never offered for approval).
  New re-approval triggers: read→write escalation (named explicitly), risk-score change, account/region change.
  `allowlist` now cross-checks tool↔capability at import, so adding a tool without classifying it is an import error.
- Verified: `make check` → **512 passed**, Ruff clean, strict mypy clean, doc budgets green. Current chains:
  `pr` = (read, write-low) risk 6 ≤ 10; `tf-review` = (read) risk 1. Tampered-score and raised-ceiling attempts refused.
- Blockers: none. Aggregation still derives from the static allowlist, not per-step observed tool use, and remains
  `pr`-scoped — the audit trajectory fields (stepId/parentStepId/toolName/resultHash) are still open.
- Next: audit trajectory schema, then post-condition expansion; GitHub App registration + EC2 rehearsal stay manual.

## 2026-07-16 — D19 command guard + approval-bound write credentials (Notion P0 잔여 2건)
- Status: Done for local/CI. No EC2/live rehearsal; GitHub App is not registered yet.
- Measured first (Claude Code 2.1.210, real headless run): `--allowedTools 'Bash(echo:*)'` **executed**
  `echo hi; whoami` with zero denials — tool patterns match the head of a command line, so `Bash(git diff:*)`
  was never an execution boundary. A PreToolUse `deny` **does** override an allowedTools allow.
- Changed: `command_guard.py` — rejects shell metacharacters/substitution/redirection/traversal before parsing,
  then matches argv against a per-command schema; installed via `--settings` PreToolUse hook (guarded command
  name travels in root-set env, unreachable from the model's subshell). `write_credentials.py` — PR push/PR-create
  is no longer standing: a repo+permission-scoped GitHub App installation token (10 min) is minted only after the
  approved plan hash is re-verified, injected into that one child env, revoked on every exit path, and audited as
  `write_credentials_issued` (jobId/approvalHash/policyVersion, never the token). Import-time cross-check keeps the
  tool allowlist and guard schema sets identical. Deploy: 4 SSM params (PEM as base64 — systemd cannot parse
  multi-line), bootstrap policy extended to ten parameters, `pyjwt[crypto]` added.
- Verified: `make check` → **492 passed**, Ruff clean, strict mypy clean (39 files), doc budgets green.
  End-to-end against the real runtime: `git status --porcelain; whoami` → denied (`forbidden shell construct: ';'`),
  `git status --porcelain $(whoami)` → denied (`'$()'`), `git status --porcelain` → ran. Not verified: the GitHub App
  token path (no App exists), and no EC2 rehearsal.
- Blockers: none in code. Manual: register the GitHub App (single repo, `contents:write`+`pull_requests:write`),
  store the 4 SSM params, then rehearse `pr` execute on EC2.
- Next: commit the bundle; GitHub App registration + EC2 pr-execute rehearsal; slides.

## 2026-07-15 — Secure-runtime bundle checkpoint verification
- Status: D16–D18 + P1/P2/P3 + Modal/Shortcut work remains uncommitted but is checkpoint-ready.
- Changed: reconciled the current verification baseline across entry-point documents; no source or deployment configuration changed in this checkpoint.
- Verified: `make check` → 417 passed, Ruff clean, strict mypy clean (37 source files), documentation budgets all green; `git diff --check` passes.
- Blockers: commit/push is intentionally pending; Slack App Message Shortcut registration, approver-button rehearsal, and slide finalization remain manual.
- Next: review the scoped bundle, commit/push it, then complete the live-demo rehearsal described in `docs/plans/2026-06-25-awskrug-demo.md`.

## 2026-07-15 — Slack Modal diff approval and Message Shortcut
- Status: Local/CI implementation done; no Slack live rehearsal performed.
- Changed: approval messages gain `Review diff`; an allowlisted reviewer can open a diff modal (up to 28K; dashboard retains the full artifact) from the button or the
  `review_slackops_job` Message Shortcut. Submission reuses the existing allowlist, conditional `awaiting_approval` transition,
  audit, and original-message update; malformed modal state fails closed.
- Verified: modal/shortcut/authorization/transition regression tests, `make check` (417 passed), and `git diff --check` pass.
  Slack App shortcut registration and real-click evidence remain manual.
- Next: commit P2 + dashboard seed + P3 + Modal/Shortcut bundle.

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
