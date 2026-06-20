# DEVPOST — SlackOps DevOps Agent (H0 submission draft)

> Draft submission copy (English = submission language). Edit into your own voice before posting.
> Companion: deck = `docs/submission/PRESENTATION.md`, demo shots = `DEMO_SCRIPT.md`, verification = `QA_TEST.md`.
> **AWS Database used: DynamoDB.**

## Inspiration
Small-team on-call lives in console round-trips and manual triage. Letting an AI *act* on
infrastructure is scary — prod changes, leaked credentials, prompt injection. "Give the bot
access" and "stay safe" usually conflict. We wanted an agent you can actually run in
production: one that **proposes and alerts**, while a human **holds the approval boundary**.

## What it does
SlackOps turns Claude Code Headless on EC2 into a Slack-controlled operations engineer.
- **Slack commands** (`/devops ping · logs · diagnose · tf-review · pr`) — read-only analysis
  and PR creation, never direct prod changes.
- **Safe-autonomy loop**: a resident agent observes signals → **proposes** a job → a
  **Slack ping + dashboard bell** fire → a human reads the rationale → an **approval gate**
  (diff review + optimistic lock) → a worker executes → telemetry (cost/tokens) is recorded.
- **Governance Detections menu**: toggle categories (IAM Access Analyzer, AWS Config, SSM
  Patch, CloudWatch alarms) ON/OFF; "Scan now" runs a **read-only** AWS scan whose findings
  land in the queue. These return real findings on any healthy account — no fault injection.
- **Dual control plane**: Slack and a Vercel web dashboard share **one DynamoDB job queue**.

## Why DynamoDB (the database choice)
Slack and Vercel share one job queue. A **DynamoDB conditional write** gives an **atomic job
claim** and an **optimistic-lock approval gate** (duplicate approvals are rejected) **without a
separate coordinator**. A single-table design serves three access patterns over GSIs
(FEED / AUDIT / METRIC) plus the detection-toggle config — so the table is not just storage,
it's the **coordination + governance control plane**. The TypeScript dashboard mirrors the
Python single-table contract, so both control planes stay consistent.

## How we built it
Python (FastAPI + Slack Bolt Socket Mode + Claude Code Headless subprocess) on EC2; AWS access
via an **agentic AWS API MCP** (read-only). Web dashboard in Next.js on Vercel reading the same
DynamoDB table. Everything runs least-privilege.

## Security & observability (differentiators)
- **Socket Mode** → no inbound port, no public endpoint.
- **IAM Instance Profile only** → zero stored access keys on EC2; write attempts are denied.
- **Permission L0/L1 only**; L2(Execute)/prod/IAM/DB changes are a hard-forbidden invariant.
- **4-layer prompt-injection defense**: untrusted-data isolation, tool allowlist, output gate
  (diff → human), enforced template prompts.
- **Full OpenTelemetry** instrumentation — latency / tokens / cost(USD) / tool-calls per run.

## Challenges
The hardest question was "what does a *healthy* deployed agent even detect?" We reframed:
we are not a new monitor — we are the **triage / safe-response layer on top of signals you
already have** (CloudWatch alarms, Config, Access Analyzer). Governance scans always surface
real findings, which made the autonomy demonstrable and honest.

## What's next
Live alarm feed (EventBridge → monitor), persistent notification dedupe, Trusted Advisor /
Security Hub categories (need a paid support plan), ADOT live numbers, L1 remediation PRs
auto-drafted from findings (still human-gated).

## Honest limitations
DynamoDB Local is in-memory (demo); prod uses the real table. Resident monitor without a live
feed is a heartbeat, not an observer. Real scan findings require cloud credentials (EC2 + IAM).
L2(Execute) is intentionally disabled. SQLite is MVP/test only.

---
### One-line DB justification (paste verbatim into description + video)
> *"Slack and Vercel share one job queue — a DynamoDB conditional write gives atomic job claim
> and an optimistic-lock approval gate without a separate coordinator."*
