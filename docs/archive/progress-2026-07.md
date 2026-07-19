# Progress archive — 2026-07

> Historical entries moved from `docs/PROGRESS_LOG.md` on 2026-07-15, 2026-07-16, 2026-07-17, and 2026-07-19. Current state lives in the active log.

## 2026-07-17 — pr execute FIXED end-to-end: a real PR opens live (the MVP write path closes)
- Status: DONE + verified LIVE. Job `f879c3fe` reached **DONE** with `Pull request opened:
  .../pull/3`; GitHub PR #3 OPEN. The 3-year-open "no real PR" gap is closed. EC2 stopped ($0).
- Three stacked root causes, each fixed and each surfaced only by fixing the one before it:
  1. **diff-source mismatch** (`ba813bf`): `_prepare` hashed the model's PRINTED diff text; execute
     byte-compared the runtime `git diff HEAD`. New `execution_plan.current_workspace_diff()` is the
     single source (prepare stores RAW/unstripped so the hash byte-matches verify). Live: verify passed,
     `write_credentials_issued` fired — first time ever past `plan_binding_rejected`.
  2. **LLM-driven git plumbing** (`9081bed`, supersedes prompt-hardening `70c29ab`): the execute model
     non-deterministically inspected instead of pushing, or left the change UNSTAGED on `main`. New
     `app.pr_execution.open_pr` does branch→add(plan.paths)→commit→push→`gh pr create` with fixed argv
     (no shell, no model), authed by the grant's child env. More reliable AND removes the LLM from the
     write path. Drift gate OK (empty observed ⊆ authorized). Live: PR #2 opened.
  3. **postcondition gh auth** (`be0422d`): `verify_remote_pr_diff` ran `gh pr diff` in the worker env
     (no grant token) → "gh auth login" → fail-closed a PR that had opened. Moved the remote check into
     `open_pr` (grant in env), path-set compare not byte-compare. Live: job #3 = DONE.
- Verified: `make check` **563 passed** + ruff + mypy strict + doc-budget. New TCs: unmocked verify
  round-trip; `open_pr` real branch/commit/push to a bare origin (gh injected) + path-mismatch fail-close.
- Live chain: Slack NL → agent propose → prepare(runtime diff) → dashboard approve (men16922) →
  deterministic execute → PR opened → grant-authed postcondition → DONE. Drove Slack/dashboard via browser.
- Notes: 2 open test PRs (#2 720-run before the postcondition fix, #3 750-run success) — unmerged, to
  close. Infra: on a stop→start EC2, `runtime-credentials-refresh` flock contention delays service
  start-pre ~2min (self-resolves); a fresh `cloud-up` avoids it.

## 2026-07-17 — (superseded, see above) approver fix + prepare hardening + finding the execute bug
- Two earlier 07-17 sessions, now fully superseded by "pr execute FIXED end-to-end": fixed the approver
  SecureString-decrypt bug (`63ec156`), pinned `claude-sonnet-5` (`bad79aa`), hardened the prepare prompt
  (`90da9cc`), added the 16KB user-data guard (`f936cf0`), and root-caused the diff-source execute bug
  (later fixed by `ba813bf`). men16922 approved via dashboard; TOCTOU plan-binding observed working. Detail
  in git history for those commits.

## 2026-07-17 — deploy #2/#3 verified LIVE on a fresh EC2 (i-00c24ec9239ad18c1)
- Status: Done. Both fixes observed working on real EC2 + real DynamoDB, then instance stopped.
- Launch snag fixed first: user-data hit the 16384-byte RunInstances limit (16714) → compressed
  to 16318 + guard test `test_user_data_within_ec2_16kb_limit` (`f936cf0`); pushed so main is launchable.
- **#2 (early boot refresh)**: boot 20:35:46Z → `runtime-credentials-refresh.timer` LAST fired
  **20:37:59Z (boot+2m13s)**, `OnBootSec=2min` confirmed on-box, 4 units active. Worker identity
  resolves to `slackops-devops-agent-runtime-role` (not bootstrap); a `ping` enqueued to real
  DynamoDB was **claimed→DONE** ("✅ pong") — no 45-min bootstrap-role Query denial.
- **#3 (orphan reclaim)**: on real DynamoDB, enqueue→claim (RUNNING)→`reclaim_stale_running` →
  **FAILED** with "orphaned running job reclaimed (worker interrupted before completion)"; worker
  restarted active. Confirms DynamoDbJobStore GSI1 query + conditional RUNNING→FAILED works live.
- Not covered: #5's real-Claude "diff in 600s" tuning (needs a human Slack pr + Approve) — worker-gate
  correctness already TC + local-e2e proven. Instance stopped (`make cloud-stop`); DynamoDB/Vercel idle ≈ $0.

## 2026-07-17 — deploy stabilization #2: credential-refresh timer fires early at boot
- Status: Done (code + test). Real EC2 verification remains (`[manual]`, systemd-only).
- Problem (#2): `slackops-runtime-credentials-refresh.timer` had `OnBootSec=45min`, so its
  first fire (which re-mints runtime creds + restarts the 4 services) was ~45min after boot.
  A service that started on boot-time creds still denied for DynamoDB Query (initial IAM
  propagation) stayed broken for 45min — matches the rehearsal's "+43min" observation; a
  manual `systemctl start …refresh.service` fixed it instantly (report §#2, prior EC2 diagnosis).
- Fix: `OnBootSec=45min` → `2min` (kept `OnUnitActiveSec=45min`; refresh service is
  `After=network-online`). Early refresh+restart converges services onto the runtime role in
  minutes, not 45. STS-safe (line-133 boot creds valid 60min cover the 2min gap). New guard
  test `test_credential_refresh_timer_fires_early_at_boot`. `make check` = **552 passed**.
- Blockers: none. Backlog now: (optional) EC2 rehearsal to observe both #2/#3 live; slides (7/19).

## 2026-07-17 — deploy stabilization #3: worker reclaims orphaned RUNNING jobs
- Status: Done (code + TC). EC2 rehearsal to observe it live remains (`[manual]`).
- Problem: credential rotation `try-restart` kills an in-flight worker job → it stays
  RUNNING forever (claim only picks APPROVED/PENDING) → orphaned, never recovered.
- Fix: `JobStore.reclaim_stale_running(older_than)` (Sqlite + DynamoDb, conditional
  RUNNING→FAILED with `ORPHANED_RUNNING_ERROR`); worker computes cutoff = now − timeout
  (`STALE_RUNNING_TIMEOUT_S=900`, env `SLACKOPS_STALE_RUNNING_TIMEOUT_S`) and calls
  `Worker.reclaim_stale()` at run_forever startup + on each idle poll, writing a
  `reclaimed_stale` audit event + failed metric per job. Chose **fail, not requeue** —
  requeuing a pr *execute* (post-approval push) risks a double push; same "no false
  success / human retries" principle as the #5 empty-diff fix. `_util.iso_before` helper.
- Verified: `make check` = **551 passed** (was 542; +9: store 3×2 backends + worker 3),
  ruff, mypy strict, doc-budget all green. Not run: real EC2 (deploy systemd unchanged —
  rotation still restarts the worker by design; the orphan is now cleaned up, not stuck).
- Blockers: none. Next: (optional) EC2 rehearsal to observe reclaim live; slides (Canvas 7/19).

## 2026-07-16 — write-cred + pr flow verified by TC; EC2 rehearsal found 6 deploy bugs
- Status: Done. Correctness of the write-cred + pr flow is verified by tests (`make check` =
  **542 passed**, ruff, mypy strict, doc-budget); real GitHub mint→revoke confirmed by local
  smoke (App `4313190`). Not done: one real-EC2 PR (optional — needs 2 human clicks + #2/#3).
- Fixed & committed: #1 MCP launch `python`→`sys.executable` (`1bb34f2`); #4 drift gate ignores
  guard-denied (is_error) tool calls (`0daf506`); #5 a pr prepare that yields no diff now FAILs
  instead of silently DONE (`2cc25ab`) + MCP registry made interpreter-agnostic. Regression tests
  added for each; the drift/trajectory tests that leaned on the old empty-diff-DONE path fixed.
- EC2 rehearsal (i-0472/i-0975, both stopped) surfaced deploy bugs, documented not fixed:
  #2 credential refresher not run at boot → ~45min on the bootstrap role → worker can't Query
  DynamoDB (claim fails); #3 45-min credential rotation restarts services, killing an in-flight
  pr prepare (job orphaned in "running"). Report: docs/reports/2026-07-16-ec2-write-cred-rehearsal.md.
- Positive on real EC2: P2 scope boundary, D23 drift gate, MCP propose_job all observed working.
- Next: (backlog) fix deploy #2/#3; optional real-EC2 PR; slides (Canvas trial 7/19). main pushed.

## 2026-07-16 — GitHub App write-credential path verified locally + SSM staged (task #3, 4/5)
- Status: Done for the local + staging steps; only the live EC2 `pr` push rehearsal remains.
- Changed: registered a GitHub App (`App ID 4313190`, installed on `men16922/slackops-devops-agent`,
  perms `contents`+`pull_requests` write only). Stored SSM 4종 (`PR_REPOSITORY`/`GITHUB_APP_ID`/
  `GITHUB_INSTALLATION_ID` String, `GITHUB_APP_PRIVATE_KEY_B64` SecureString). Enabled branch protection
  (require PR + approvals=1) so the token cannot self-merge. No source change.
- Verified: **local mint smoke against real GitHub** — `GitHubAppGrantIssuer.issue` minted a repo-scoped
  installation token (len 40, ~10-min expiry) then revoked it → App ID + installation + PEM all valid.
  This closes the "previously-unverified code path" for everything except the actual push. SSM values re-read OK.
- Blockers: none. The private-key base64 was piped straight into SSM (never written to a scratch file —
  auto-mode classifier blocked materializing the key on disk).
- Next: EC2 `pr` execute live rehearsal (Done conditions 1–3) at presentation time — `docs/runbooks/pr-write-credential-rehearsal.md`.

## 2026-07-16 — Slack workspace migration + docs consolidation (v2 intro/test)
- Status: Done (docs + local/cloud-SSM). Uncommitted working tree; GitHub App write path still pending.
- Changed: **Slack migrated to a new workspace** ("Platform Agent", team `T0BGA6C1YAG`) — App re-created from a
  manifest, SSM Slack 4종 (`SLACK_BOT_TOKEN`/`SLACK_APP_TOKEN`/`SLACK_APPROVER_IDS`/`SLACK_NOTIFY_CHANNEL`)
  overwritten to v2; new guide `docs/guide/kr/SLACK_NEW_GUIDE.md` + `slack-app-manifest.yaml`.
  **Docs consolidated**: added `docs/V2_INTRO.md` (v1 해커톤 → v2 AWSKRUG 강화 비교) and `docs/V2_TEST.md`
  (검증 통합 — gate/스위트맵/e2e); archived `docs/guide/en/` (4, Korean-only policy) → `docs/archive/guide-en/`
  and the one-off secure-runtime report → `docs/archive/`; refreshed `docs/README.md` index; fixed dangling refs
  from the deleted awskrug plan. Added task-#3 runbook `docs/runbooks/pr-write-credential-rehearsal.md`;
  `.gitignore` now ignores `*.pem` (GitHub App private key).
- Verified: new bot token `auth.test` OK (team "Platform Agent"); new-workspace `/devops ping` → pong;
  `make demo` full stack up (dashboard 8930 = 200, DDB 8931 seeded, worker/chat pollers); doc-budget green
  (55/112/42/…); no broken links to moved paths; cleanup inventory found no dead source (all refs live).
- Blockers: none. GitHub App write path (task #3) is the only unverified code path — App created but SSM 4종 +
  EC2 `pr` execute rehearsal pending.
- Next: (1) resume task #3 — need numeric App ID + target repo → SSM 4종 → EC2 rehearsal; (2) register
  `review_slackops_job` Message Shortcut in the new workspace; slides (Canvas trial ends 7/19).

## 2026-07-16 — Entry-doc tidy + secure-runtime bundle committed
- Status: Done. Working tree clean; `main` is **10 commits ahead of origin — not pushed**.
- Changed: committed the whole secure-runtime bundle as three commits (`3affc65` D16–D21 + P1/P2/P3,
  `84535bc` D22, `86b08be` D23), then ran `/tidy-docs` (`0d6ea2e`). Every entry doc was at or near cap, so the next
  checkpoint would have failed the gate. PROGRESS_LOG 118→61 (newest 3 kept; D20/D19 + two 07-15 entries → archive),
  NEXT_PLAN 70→42 (14 `[x]` items → one COMPLETED_SUMMARY milestone), STATUS 120→110 and AGENT_BRIEF 60→56 (D19–D23
  detail → DECISIONS link), COMPLETED_SUMMARY 19→39 (3 milestones incl. what stayed unverified).
- Verified: `make check` → **540 passed**, Ruff, strict mypy (39 files), doc budgets green (56/110/42/61).
  Archive/plan/decision/runbook links all resolve; DECISIONS retains D19–D23 rationale.
- Blockers: none in code. The one unverified code path is the **write-credential path** (no GitHub App registered);
  it is now called out separately in NEXT_PLAN rather than buried among finished checkboxes.
- Next: push `main`; then GitHub App + 4 SSM params + EC2 `pr` execute rehearsal; slides (⏰ Canvas trial ends 7/19).

## 2026-07-16 — D23 promote observed capability from record to gate
- Status: Done for local/CI. No EC2/live rehearsal.
- Changed: worker now checks what actually ran before a result may count as a completed job. Observed capability is
  resolved via the guard's parse and held to the **approved plan's** capability set/risk (or, with no plan, the
  command's static allowlist as the ceiling). Any tool call the guard does not authorize, any capability outside the
  authorized set, or any risk above the approved score fails the job with a dedicated `capability_drift` audit event
  carrying the reason. Tool steps are recorded on the failure path too — a rejected run must not leave a hole in the
  trajectory. `CapabilityDrift` is its own exception so drift is distinguishable from plan-binding rejection.
- Verified: `make check` → **540 passed**, Ruff, strict mypy, doc budgets. Drove both paths: authorized
  (`git status` only) → DONE with `caps=read`; guard-bypass (`curl http://169.254.169.254/` observed) → FAILED with
  `capability_drift: observed a tool call the guard does not authorize`, and both tool steps still in the tree.
- Blockers: none. On the normal path this gate is silent because `command_guard` already rejects the argv — that is
  the intent (defence in depth), not redundancy: it only speaks if the guard is bypassed or the tool surface drifts.
- Next: GitHub App registration + 4 SSM params + EC2 `pr` execute rehearsal (manual); slides.

## 2026-07-16 — D22 per-tool-call trajectory + observed capability (Notion P1 close-out)
- Status: Done for local/CI. No EC2/live rehearsal.
- Measured first (2.1.210 stream-json): `assistant` events carry `tool_use{id,name,input.command}` and `user`
  events carry `tool_result{tool_use_id,is_error,content}` — enough to reconstruct what actually ran.
- Changed: `run_headless` now uses `--output-format stream-json --verbose`. The reason is **observation, not
  streaming**: the `json` result object has no tool-call data, so the app could not know what executed.
  `_parse_result` accepts both JSONL and the old single-JSON object, because injected-runner tests use the latter
  shape and a parser that knows only one would let mocks and production drift apart. New `ToolCall`
  (tool_use_id/name/command/result_hash/is_error) flows RunResult → RunMetrics → CommandOutcome.tool_steps → worker,
  which emits one `tool_call` audit step per observed call under the claim root. `ArgSchema` now names the allowlist
  tool it authorizes, so `command_guard.resolve_tool` maps an observed argv back to a declared capability using the
  parse the guard already had to do — no second, drifting classifier. `done` records **observed** capabilities;
  `awaiting_approval` records `observed_capabilities` beside the planned risk. Unresolvable argv is recorded as
  `unresolved:<name>` rather than dropped. pr's two Claude calls (prepare+execute) both contribute steps.
- Verified: `make check` → **536 passed**, Ruff, strict mypy, doc budgets. Real `claude -p` e2e: two real Bash calls →
  `claimed(pr) → tool_call Bash(git status:*) → tool_call Bash(git diff:*) → done caps=read`, chain verified.
  Observed `read` (only reads ran) vs the allowlist's static `read,write-low` — the D20 gap is closed.
- Blockers: none. Audit-step failures are swallowed so recording cannot fail an execution; capability re-aggregation
  is observational only — it does not (yet) re-gate a job that exceeds its approved risk mid-run.
- Next: consider gating on observed-vs-approved capability drift; GitHub App registration + EC2 rehearsal stay manual.

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
- Next: review the scoped bundle, commit/push it, then complete the live-demo rehearsal described in `docs/plans/2026-06-25-awskrug-demo.md` (deleted 2026-07-16).

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
- Next: commit this scoped bundle, then AWSKRUG slide/rehearsal. Details: `docs/archive/2026-07-15-secure-runtime-report.md`.

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
