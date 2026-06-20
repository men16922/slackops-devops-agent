# QA_TEST — Manual Verification (Pending items only)

> **Documents only the items that require manual verification and are not yet completed.**
> Automated gates (`make check` — pytest/ruff/mypy) and **local full e2e are completely ✅ done** (refer to PROGRESS_LOG) → excluded here.
> How to run: Agent = [SLACK_GUIDE.md](SLACK_GUIDE.md) · Dashboard = [DASHBOARD_GUIDE.md](DASHBOARD_GUIDE.md) ·
> Infrastructure execution/submissions = `docs/runbooks/deploy-checklist.md` (authoritative).

---

## 1. Remaining Verification — After AWS Deployment (Only remaining track)
> Cloud e2e (`/devops ping`, IAM Instance Profile for CloudWatch RO via AWS MCP) was **verified on 2026-06-20 and the EC2 instance was stopped**.
> Below are pending items to verify **once upon restart** for securing submission artifacts.

- [ ] **Real DynamoDB Data** — Load real items (Job/Audit/Metric) into `slackops-agent` → **Console Screenshot** (submission artifact).
- [ ] **Measured Metrics** — Run `diagnose` once: duration N seconds / cost $0.0X / tool call M times (from `devops.run` span or dashboard Telemetry).
- [ ] **Vercel Dashboard** — Read real DynamoDB to render feed + **Get Team ID/link** (DASHBOARD_GUIDE §7).
- [ ] **Output Gate + branch protection** — Cannot merge without approval (for real GitHub, when verifying PR gate).
- [ ] *(Optional)* **EventBridge** — Operates weekday stop/start schedules (do not run continuously). Currently replaced by shutting down — to be determined on restart.
- [ ] *(Optional)* **ADOT Collector** — Verify metrics via CloudWatch EMF + X-Ray (`deploy/adot/collector-config.yaml`).

> Submission checklist (diagrams/screenshots/demo video/text/links/articles) is in `deploy-checklist.md` [E]·[F].

---

## 2. Judging Requirements — DB Justification (Directly use in submission description/video)
> Slack and Vercel control planes share a single job queue → implemented atomic job claim + optimistic-lock approval gate via **DynamoDB conditional write** without requiring a separate coordinator. (Reason for choosing DynamoDB over Aurora)

- **Technical** — Single-table + conditional write (atomic claim / prevention of duplicate approvals). GSI2 = FEED/AUDIT/METRIC feed.
- **Design** — Web TS `lib/ddb` mirrors Python `store/` single-table contract (homomorphic GSI queries and ConditionExpression).
- **Impact** — Target = small team on-call/platform engineers. Reduces round-trips to AWS console and manual diagnostic efforts. Open ports 0 + least privilege + human approval → safe deployment.
- **Originality** — Shared single queue for autonomous agent *proposals* and human *oversight*. A reference safety pattern for operational agents, not just a simple chatbot.

---

## 3. Known Limitations / Cautions (Honest disclosure in submission description)
- **CloudWatch ingested via AWS MCP `tool_result` (D13) → bypasses `<untrusted_data>` isolation.** Boundaries = IAM read-only + `READ_OPERATIONS_ONLY` + `--strict-mcp-config` + read-only tool allowlist.
- DynamoDB Local is **in-memory** — data is lost on `docker compose down`/restart, and mock seed data is re-injected on `up`. Web chat has polling self-recovery + retry for seamless new conversations.
- `tool_calls` telemetry: streaming path (`chat_agent`) is collected; worker (non-streaming `run_headless`) metrics are still `None`.
- Level 2 (Execute)/prod/IAM/DB changes are **inactive** (immutable ban) — out of MVP scope.
- Local worker's `pr execute` performs a real push, so it can only be verified in a GitHub-authenticated environment (=AWS/EC2).
- SQLite is for **MVP/testing only** — do not refer to it as the production datastore (production = DynamoDB).
