# PROGRESS_LOG — slackops-devops-agent
Last updated: 2026-07-17

> Latest 3–5 increments (≤120 lines, newest on top). When it overflows, split into docs/archive/progress-YYYY-MM.md. Append via /checkpoint.
> Earlier entries (~2026-06-20): docs/archive/progress-2026-06.md
> Archived 2026-06-26–2026-07-16 entries: docs/archive/progress-2026-07.md

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

## 2026-07-17 — fresh-EC2 pr run: prepare hardening worked; found the real execute-blocking bug
- Status: Root cause found (no code change this session). Instance i-0269c8e791e26cc84 launched with all
  current main fixes from boot, then stopped ($0). No real PR yet — but now we know exactly why.
- What worked (fresh boot, no manual steps): `SLACK_APPROVER_IDS` decrypted from boot (`63ec156`);
  `claude-sonnet-5` pinned; **the prepare-prompt hardening (`90da9cc`) worked — the model made the edit
  and produced a 298-char diff → AWAITING_APPROVAL** (vs 3/4 no-diff before). men16922 approved via dashboard.
- **THE BUG (execute always fail-closes):** `_prepare` hashes/approves the diff **text the model prints
  between the markers**, but `verify_pr_workspace` (execute) recomputes the runtime's own
  `git diff HEAD --no-ext-diff --binary` and **byte-compares** (`execution_plan.py:340`). The model emits an
  approximation — fake `index 0000000..0000000`, a different `@@` function-context line, a shifted context
  line — so the two never match → `plan_binding_rejected` every time. Confirmed by diffing both on-box.
  Masked until now because TC mocks the verifier, so the byte comparison never ran. This is why no real PR
  has ever opened through the execute path — it is a verification-source mismatch, not infra/approval/drift.
- Verified: on-box `git diff HEAD` (real `index 33bbea3..36d8fdf`) vs stored approved diff (`index 0000000`).
- Blockers: the diff-source mismatch. Next: fix `_prepare` to use the RUNTIME's `git diff HEAD --no-ext-diff
  --binary` as the authoritative diff (display + hash + execute), not the model's printed text; add a TC that
  exercises the real (unmocked) verify against a temp git repo. Then re-run the live PR (should pass).

## 2026-07-17 — live Slack/dashboard pr test: approver bug fixed, model pinned, prepare hardened
- Status: Done (code + partial live). Fresh EC2 launched, driven, then stopped ($0). One clean real
  PR not reached — root cause is prepare non-determinism (below), not infra.
- **Approver bug (root-caused + fixed)**: `SLACK_APPROVER_IDS` is a SecureString but user-data fetched
  it **without `--with-decryption`**, so the instance baked KMS ciphertext into the allowlist → every
  approval denied ("approver is not in the allowlist") even for the correct id. Fix `63ec156` (+ guard
  test that all SecureString params decrypt) + patched the running instance env. After the fix,
  **men16922 approved job 2ade0913 via the GitHub dashboard** (browser-driven) — approval path confirmed.
- **plan-binding security observed working**: that approved execute then fail-closed with
  `working tree diff changed after approval` (D19–23 TOCTOU) because the shared worktree drifted over the
  22-min prepare→approve gap — no wrong PR pushed.
- **Sonnet 5 pinned** (`bad79aa`): headless runs had no `--model`; now `claude-sonnet-5` (env-overridable).
- **prepare hardened** (`90da9cc`): 3 of 4 live prepares emitted 0 tool calls + no diff (model advised
  instead of editing; Claude itself healthy). Prompt now orders it to MAKE the edit autonomously; a
  solvable change MUST produce a diff. Guard test added.
- **16KB user-data guard** (`f936cf0`): the #2 comment pushed user-data over the RunInstances limit;
  compressed + size guard test. `.claude/settings.local.json` gained an autoMode allow for SSM ops.
- Verified: `make check` = **557 passed**, ruff, mypy strict, doc-budget green. Instance stopped.
- Next: on next EC2 boot everything applies from boot (decrypted approver, Sonnet 5, stronger prepare) —
  one `pr` should reach a real PR more reliably. Docs tidied (PROGRESS_LOG 108→49).

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
