# PROGRESS_LOG — slackops-devops-agent
Last updated: 2026-07-16

> Latest 3–5 increments (≤120 lines, newest on top). When it overflows, split into docs/archive/progress-YYYY-MM.md. Append via /checkpoint.
> Earlier entries (~2026-06-20): docs/archive/progress-2026-06.md
> Archived 2026-06-26–2026-07-16 entries: docs/archive/progress-2026-07.md

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
