# PROGRESS_LOG — slackops-devops-agent
Last updated: 2026-07-16

> Latest 3–5 increments (≤120 lines, newest on top). When it overflows, split into docs/archive/progress-YYYY-MM.md. Append via /checkpoint.
> Earlier entries (~2026-06-20): docs/archive/progress-2026-06.md
> Archived 2026-06-26–2026-07-16 entries: docs/archive/progress-2026-07.md

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
