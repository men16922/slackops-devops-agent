# PROGRESS_LOG — slackops-devops-agent
Last updated: 2026-07-16

> Latest 3–5 increments (≤120 lines, newest on top). When it overflows, split into docs/archive/progress-YYYY-MM.md. Append via /checkpoint.
> Earlier entries (~2026-06-20): docs/archive/progress-2026-06.md
> Archived 2026-06-26–2026-07-16 entries: docs/archive/progress-2026-07.md

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
