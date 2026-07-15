# PROGRESS_LOG — slackops-devops-agent
Last updated: 2026-07-16

> Latest 3–5 increments (≤120 lines, newest on top). When it overflows, split into docs/archive/progress-YYYY-MM.md. Append via /checkpoint.
> Earlier entries (~2026-06-20): docs/archive/progress-2026-06.md
> Archived 2026-06-26–2026-07-15 entries: docs/archive/progress-2026-07.md

## 2026-07-16 — D21 full-trajectory audit fields (Notion P1)
- Status: Done for local/CI (store + worker + web mirror). No EC2/live rehearsal.
- Changed: `AuditEvent` gains `step_id`/`parent_step_id`/`tool_name`/`capabilities`/`target_resource`/`result_hash`;
  the store assigns `step_id` (callers cannot forge a parent link). Worker now emits a trajectory instead of a flat
  transition list: `claimed` is the job root, later steps descend from it, and `write_credentials_issued` descends from
  the **approval step that authorized it** — a real push walks back to the decision. `result_hash` pins what a step
  returned without storing the body; `plan_binding_rejected` now records the reason. `build_step_tree` reconstructs it.
  Also fixed a mutable-per-job-state slip: trajectory context is threaded as locals, not Worker attributes.
- Back-compat: trajectory fields join `event_hash` **only when set**, so chains already in DynamoDB still verify —
  a schema change that silently invalidated every historical chain would make tamper-evidence worthless. Web
  `AuditEvent` mirror updated with the fields optional (it was already missing context/event_hash).
- Verified: `make check` → **524 passed** (incl. Sqlite↔DynamoDB/moto equivalence for the new fields), Ruff, strict
  mypy, doc budgets; `npx tsc --noEmit` clean. Drove a real Worker run and printed the reconstructed tree:
  `claimed(logs) → done(target=log_group:checkout-api, result=e3ac7de…)`, chain verified.
- Blockers: **per-tool-call sub-steps are NOT implemented** — `--output-format json` carries no tool-call data, so a
  true step tree under one Claude call needs stream-json parsing. Today's tree is phase-level, not call-level.
- Next: per-step trajectory via stream-json (would also let capability aggregation use observed tools, not the static
  allowlist); GitHub App registration + EC2 rehearsal stay manual.

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
