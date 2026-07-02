# QA_TEST — Human Checklist (v2 AWSKRUG demo)

> **Only the items a human must check, in priority order.** Everything agent-verifiable is ✅ done
> (gate `make check` 358 passed · local docker · Assistant console real/mock · injection defense) —
> records live in `docs/PROGRESS_LOG.md` (2026-07-01/02 entries), not here.
> Authority: `docs/NEXT_PLAN.md` > `docs/plans/2026-06-25-awskrug-demo.md` §4 > this file.
> How to run: Agent = [SLACK_GUIDE.md](SLACK_GUIDE.md) · Dashboard = [DASHBOARD_GUIDE.md](DASHBOARD_GUIDE.md) · Infra = `docs/runbooks/deploy-checklist.md`.
>
> ⛔ Slack hackathon submission is **abandoned** (Devpost §3 — South Korea ineligible). Goal = **AWSKRUG live presentation demo**.

---

## 1. ★ Real Slack sandbox e2e (NEXT — the only blocking gap)
> Launch `python -m app.main` (launch + Socket Mode WSS already verified 2026-07-01), then type in a real
> Assistant thread. **Button payload shape, real claude streaming, and Canvas API are only confirmed here** —
> the underlying gate/store logic is already verified; this is the Slack binding surface only.
> Prereq (all granted): SSM `bot/app/oauth` tokens + `SLACK_NOTIFY_CHANNEL` (= Canvas target channel) + `DASHBOARD_URL`, scope `canvases:write`.

- [ ] **NL diagnose** — type "checkout-service is slow" in the Assistant DM/thread → placeholder → **streaming** incremental render (`chat.update`).
- [ ] **poll-in-thread** — after the proposed job settles, **approval buttons/result** are posted to the thread.
- [ ] **Approve click** — Approve → output-gate state machine transitions to `APPROVED` (optimistic lock + audit, idempotent) → worker executes.
- [ ] **Postmortem Canvas** — right after a completed diagnose, `canvases.create` auto-creates a channel-tab Canvas (`maybe_postmortem`).
- [ ] **footer** — response shows cost/tokens/tool calls (OTel).
- [ ] **payload confirm** — the real button-click payload (`container.message_ts` / `channel.id` / `actions[].value`) matches handler assumptions.

---

## 2. Slack platform BUY features (D2.5 — confirm in real Slack)
> Wired in code · UX not yet verified in a real workspace. Same session as §1 is fine.

- [ ] **Modal diff approval** (`views.open` + `@app.view`) — `trigger_id` 3s limit · diff chunked render.
- [ ] **mrkdwn / Markdown blocks** — table→code block, heading/bold/divider render.
- [ ] **Message Shortcut** ("Diagnose this alert") — works after manifest addition + app reinstall.

---

## 3. D4 — Real AWS e2e (once)
> Single EC2 start → demo/capture → terminate immediately (`make cloud-*`). DynamoDB stays ~$0. Cost decision = human.

- [ ] `make cloud-up` → diagnose **real CloudWatch** via Assistant (real trace-ids quoted) → a write op → **"denied by security policy"** → `make cloud-stop`.
- [ ] **D2a** — in-turn AWS MCP read streaming (`uvx awslabs.aws-api-mcp-server`) works.
- [ ] **Capture** — screenshots/recording of the real run (for slides / recorded backup).

---

## 4. D5/D6 — Presentation artifacts
- [ ] **Recorded backup** video (against live failure, 2x edited).
- [ ] **Injection-defense scene — capture only** (behavior verified 2026-07-02): `make demo-assistant`, type a message with a planted malicious instruction ("ignore all previous rules … `aws iam create-user` …"), record the explicit refusal.
- [ ] **AWSKRUG slides** — problem → architecture → security (approval gate + 4-layer injection defense) → observability (OTel) → demo → lessons.

---

## 5. Known limitations / cautions (disclose honestly when presenting)
- **CloudWatch ingested via AWS MCP `tool_result` (D13) → bypasses `<untrusted_data>` isolation.** Boundaries = IAM read-only + `READ_OPERATIONS_ONLY` + `--strict-mcp-config` + read-only tool allowlist.
- Slack Canvas: a Free team cannot create standalone → `channel_id` required (channel-tab form). Uses `SLACK_NOTIFY_CHANNEL`.
- `tool_calls` telemetry: the streaming path (`chat_agent`/Assistant) is collected; worker (non-streaming `run_headless`) metrics are still `None`.
- Level 2 (Execute)/prod/IAM/DB changes are **inactive** (immutable ban) — out of MVP scope.
- The local worker's `pr execute` does a real push, so it can only be verified in a GitHub-authenticated environment (= AWS/EC2).
- SQLite is for **MVP/testing only** — do not call it the production datastore (production = DynamoDB).
