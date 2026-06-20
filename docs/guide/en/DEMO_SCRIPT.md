# DEMO_SCRIPT — 3-min demo shot list (H0)

> One continuous take where possible. On-screen captions in **English**. Record the loop locally
> (`make demo`), capture the 4 cloud-only proofs on a 1-run EC2, then edit together.
> Deck: `docs/submission/PRESENTATION.md` (Appendix C = local/cloud split). Don't read the README aloud.

## Setup (before recording)
```sh
export CLAUDE_CODE_OAUTH_TOKEN="$(claude setup-token)"
make demo            # web(8930) + DynamoDB Local + chat_agent + worker
# (optional Slack ping) run app.main locally with real Slack tokens + SLACK_NOTIFY_CHANNEL
```

## Shots

**0:00 — Problem (20s).** Small-team on-call toil; thesis caption: *"AI proposes & alerts, a human holds the boundary."*

**0:20 — Trigger (cloud, honest).** Terminal:
`aws cloudwatch set-alarm-state --alarm-name checkout-5xx --state-value ALARM`
Caption: *"In prod this fires on a threshold; here we force the transition to show the pipeline."*

**0:40 — Detect + notify.** Resident `agent_monitor` proposes a job → **Slack channel ping** +
**dashboard 🔔 bell** light up (unread count). Caption: *"Detected → proposed → alerted."*

**1:05 — Governance angle.** Open **Detections** → toggle a category ON → **Scan now** →
a `detect` job appears in the queue; (cloud capture) its result lists **real findings**
(IAM Access Analyzer / Config). Caption: *"Read-only scan; findings, not actions."*

**1:35 — Human gate.** Open the proposal → read the **rationale + diff** → ✅ **Approve**.
Show the **optimistic lock**: a second approve → "already handled". Caption: *"Human holds the boundary."*

**2:00 — Execute + proof.** `worker` runs Claude + **AWS API MCP (read-only)** → DONE.
(cloud) show a write attempt → **"denied by security policy."**

**2:20 — Telemetry + audit.** Per-run cost/tokens on the Telemetry page + the Audit timeline
(who approved, when).

**2:40 — Close.** Overlay the invariants: Socket Mode (no inbound) · IAM Instance Profile (no keys)
· injection isolation · L0/L1 only. End on the DB one-liner (see DEVPOST).

## What must be a CLOUD capture (EC2 1-run, ~$1, stop after)
1. Real CloudWatch `diagnose` via Instance Profile.
2. Real governance scan **findings** (IAM Access Analyzer / Config).
3. **write-denied** ("denied by security policy").
4. alarm `set-alarm-state` → EventBridge/monitor proposal.
Everything else (chat, proposal, bell, approve, lock, execute, telemetry, Detections toggle/Scan-now job) records locally with `make demo`. Slack ping records locally too (Socket Mode is outbound).
