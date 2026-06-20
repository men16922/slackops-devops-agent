# DASHBOARD_GUIDE — Web Dashboard Guide

> **One document, two audiences.** ① **The operator interacting with the dashboard** → §1~§6 (local, no real AWS required).
> ② **The administrator deploying the dashboard to Vercel** → §7. Agent backend is in [SLACK_GUIDE.md](SLACK_GUIDE.md), remaining verification is in [QA_TEST.md](QA_TEST.md), infrastructure launch is in `docs/runbooks/deploy-checklist.md`.

Dual control plane: Slack (Socket Mode) + web dashboard (Next.js) share a **single job queue (DynamoDB single-table)**.

---

## 1. Quick Start (No real AWS required)
```sh
cd web
docker compose up --build
```
- Browser: **http://localhost:8930**
- Composition: `dynamodb-local` (offline) → `seed` (mock Job/Audit/Metric) → `web`. **No credentials required** (dummy keys).
- In case of port 8930 conflict, replace only the `web.ports` line in `web/docker-compose.yml` (e.g., `"9930:3000"`).

> **One-step execution (including real Claude):** run `make demo` after `export CLAUDE_CODE_OAUTH_TOKEN="$(claude setup-token)"`
> — Starts web + DynamoDB Local + `chat_agent` + `worker` simultaneously, cleans up on Ctrl-C.

---

## 2. Reading the Screen
Two top menus — **Job Queue** (job list & status) / **Telemetry** (usage statistics).

| Badge | Meaning | Action |
| --- | --- | --- |
| 🟡 `awaiting_approval` | Awaiting human approval | **Click to verify** |
| 🔵 `running` | Running | Wait |
| 🟢 `done` | Completed | — |
| 🔴 `failed` | Failed | Check reason in details |

- Click on blue **command text** (`pr`/`diagnose`/`logs`) → Details page.
- 🤖 **agent badge + rationale** = Autonomous agent proposed job (displays rationale for proposing).

---

## 3. Job Details + Approval Demo ⭐ (Core Safety Gate)
Click job → basic info (command/requester/cost/tokens) + **Audit Timeline** at the bottom.
🟡 For jobs awaiting approval: **📝 diff preview + ✅ Approve / ❌ Reject**.

1. Click 🟡 job → read diff → click ✅ **Approve** → status becomes `approved` + "who approved when" added to timeline.
2. Refresh and try **approving the same job again** → Rejected with **"Job already handled"** = **Optimistic Locking** (prevents duplicate execution) in action.

> **Even if the AI writes the code, it runs only when a human clicks the button** — Output Gate (Layer 3 of injection defense).

---

## 4. Interactive Producer — Chatting with the Agent for Job Proposals
Type natural language in the **Chat** box at the top of the main screen (e.g., `api 5xx is rising, find the cause`). The input does not go directly to Claude; instead, it is loaded into the **DynamoDB Chat Bus**, where the agent (`chat_agent`) polls it, isolates it via sanitizer, and sends a **streaming response** back through Claude (rendering Markdown by polling the growing response every ~800ms). If the agent decides a specific job is necessary, it proposes it to the Job Queue via `propose_job` → displays a "🤖 A job has been proposed" callout → **Approve/Reject** in the queue below.

> 🔒 Free text is **never passed directly** to Claude — routed through Chat Bus + isolated via sanitizer + agent can only call `propose_job` (read-only). Since it only performs DynamoDB **polling (outbound)**, it maintains inbound port 0 / Socket Mode invariance → **works even on Vercel deployments**.

---

## 5. End-to-End Execution Loop — Chat/Proposal → Approval → Execution
To run with real Claude (requires `CLAUDE_CODE_OAUTH_TOKEN`):
```sh
export CLAUDE_CODE_OAUTH_TOKEN="$(claude setup-token)"
make chat-agent ARGS=--once     # Chat: Process 1 waiting conversation (streaming response + propose_job if needed)
make agent-monitor              # (Alternative) Detect signals → Autonomous proposal (pending)
# Approve the proposal on the web UI at port 8930
make worker ARGS=--once          # Execute approved job → done + updates audit/metric
```
- Level 0 (`diagnose`/`logs`) runs immediately → `done`, Level 1 (`pr`) prepares → `awaiting_approval`, and approved jobs execute → `done`.
- In ops (EC2), `chat-agent`/`worker` run continuously as systemd services. For loop details, see `docs/runbooks/agent-mcp-demo.md`.

---

## 6. Telemetry + FAQ
**Telemetry** — Upper cards (runs/total cost/tokens/tool calls/success rate) + bottom command rollup & recent runs. Cost is usually a few cents per run.

- **The list is empty** — Seed not run or DB connection lost. Refresh after a moment.
- **The buttons are rejected** — Someone else has already approved/rejected, or the status changed (normal behavior, optimistic lock).
- **Is the data real?** — By default, it's **mock seed data**. In real operations/deployments, Slack and agent commands are loaded in real time.
- **Shutting down** — `cd web && docker compose down`. Since it uses an in-memory DB, data will be lost on shutdown and recreated on startup.

---

## 7. Vercel Deployment — Reading Real DynamoDB (Operator, for Submission)
**Not required** for local offline mode (§1). Below is the procedure to allow the **Vercel deployed dashboard** to read the real DynamoDB.
Structure: Browser → Vercel (Next.js server) → **AWS SDK + Read-only Key** → DynamoDB.
(Not EC2 → Instance Profile cannot be used, so AWS Access Key is used **here only** — read-only and scoped to the table.)

### 7-1. Read-Only IAM User Key
IAM → Users → Create user (Console OFF, programmatic access only) → Inline policy:
```json
{ "Version": "2012-10-17", "Statement": [{
  "Sid": "DashboardRead", "Effect": "Allow",
  "Action": ["dynamodb:GetItem", "dynamodb:Query"],
  "Resource": ["arn:aws:dynamodb:*:*:table/slackops-agent",
               "arn:aws:dynamodb:*:*:table/slackops-agent/index/*"] }]}
```
- To allow approvals (write) as well, add `dynamodb:UpdateItem` and `dynamodb:PutItem` to `Action`.
- Security credentials → **Create access key** ("Application outside AWS") → obtain `AKIA…`/secret (secret is shown only once — keep safe, do not commit).

### 7-2. Vercel Project + Environment Variables
- New Project → Link repository → **Root Directory = `web`**.
- Settings → Environment Variables:
  | Key | Value |
  | --- | --- |
  | `DDB_TABLE` | `slackops-agent` |
  | `AWS_REGION` | `us-east-1` (Must match the table creation region) |
  | `AWS_ACCESS_KEY_ID` | `AKIA...` |
  | `AWS_SECRET_ACCESS_KEY` | `...` |
  | `DASHBOARD_APPROVER` | Name of the approver to display |
- ⚠️ **Do NOT set `DDB_ENDPOINT`** — if left unset, it connects to the real DynamoDB (setting it targets local mode).
- Deploy → **Record deployment URL + Team ID** (submission details).

> **Verifying real DynamoDB locally:** Copy `web/.env.local.example` → `web/.env.local` and fill in Mode B blocks (remove/comment out `DDB_ENDPOINT`). `.env.local` is never committed.

### 7-3. Key Rotation / Revocation
After evaluation or in case of suspected exposure: IAM → Key **Deactivate → Delete** → Replace with a new key.
