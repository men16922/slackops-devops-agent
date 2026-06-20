# NEXT_PLAN — slackops-devops-agent
Last updated: 2026-06-20

> **Open work only** (≤120 lines). Remove when done (history → PROGRESS_LOG/COMPLETED_SUMMARY). Authority: this file > docs/plans/.
> Tags: `[auto]` = doable in an unattended overnight round (local code+tests). `[manual]` = operator manual (AWS/Slack/UI).
> `[blocked]` = same item hit a Blocker twice — no unattended retry before human review (rounds append and skip).
> Unattended rounds do one `[auto]` top-to-bottom. Each item's "Done:" criterion must be met to finish.

## ★ Active — H0 hackathon pivot (submit 2026-06-29 / judging ~7-24, submission plan docs/plans/2026-06-17-h0-submission.md, pivot docs/plans/2026-06-12-h0-hackathon.md, DECISIONS D5·D6·D7)
> Backend (store/worker/commands) + **web/ dashboard local complete**: Next.js App Router, jobs/detail
> (diff output gate + Approve/Reject)/metrics, DynamoDB Local offline docker (port 8930) — e2e verified.
> AWS credit request **rejected** → proceed with $63.91 on hand + free tier (inference is subscription OAuth = D6).
- [x] DynamoDB table provisioned (`slackops-agent`, us-east-1, PAY_PER_REQUEST, GSI1/2) 2026-06-20.
- [ ] **Phase 3-deploy** — relaunch EC2 (`deploy/ec2/launch-instance.sh`, t3.medium; user-data installs uvx + pre-warms AWS MCP)
      → Slack cloud e2e of the MCP path (`/devops diagnose checkout-service` via `mcp__awsapi__*`). EC2 currently terminated.
- [ ] `[manual]` Vercel deploy: web/ → connect real DynamoDB (`DDB_ENDPOINT` unset + read-key env, USER_GUIDE §5) → obtain Team ID/link.
- [ ] `[manual]` Capture numbers (diagnose N sec/$0.0X/M tool calls) + real DynamoDB data (on redeploy).
- [ ] `[manual]` Submission: architecture diagram, DynamoDB screenshot, 3-min demo video, text description, Vercel link/Team ID, (bonus) article.
- [ ] `[manual]` After submission (6/29) EC2 stop, keep DynamoDB/Vercel (judging-period cost ~$0 — USER_GUIDE §7).

## Day 1–3 — AWS/Slack execution (deploy/README.md order) — A–C DONE 2026-06-20
- [x] Slack App (Socket Mode) created + SSM SecureString tokens (bot/app/CLAUDE_CODE_OAUTH_TOKEN) stored.
- [x] `deploy/iam/create-role.sh` (role+profile, +AmazonSSMManagedInstanceCore for Session Manager).
- [x] `deploy/ec2/launch-instance.sh` (repo public-transitioned for unauth clone; 3 systemd services active) → `/devops ping` pong verified → EC2 terminated.
- [ ] `[manual]` `deploy/eventbridge/create-schedules.sh <id>` — skipped (terminate instead of schedule; revisit on redeploy).
- [ ] `[manual]` On redeploy: confirm worker + chat_agent resident (3 `systemctl status` active + web chat responds).

## Day 6–7 — tf-review + pr remaining
- [ ] `[manual]` GitHub App minimal scope + branch protection (block auto-merge) setup.

## Day 8–9 — Observability
- [ ] `[manual]` Configure ADOT Collector on EC2 + capture diagnose numbers once (N sec/$0.0X/M tool calls).

## Later — presentation/article (manual)
- [ ] `[manual]` Record demo + slides / AWSKRUG talk / PACE paragraph / article draft.
