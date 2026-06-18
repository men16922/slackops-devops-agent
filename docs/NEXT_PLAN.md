# NEXT_PLAN — slackops-devops-agent
Last updated: 2026-06-16

> **Open work only** (≤120 lines). Remove when done (history → PROGRESS_LOG/COMPLETED_SUMMARY). Authority: this file > docs/plans/.
> Tags: `[auto]` = doable in an unattended overnight round (local code+tests). `[manual]` = operator manual (AWS/Slack/UI).
> `[blocked]` = same item hit a Blocker twice — no unattended retry before human review (rounds append and skip).
> Unattended rounds do one `[auto]` top-to-bottom. Each item's "Done:" criterion must be met to finish.

## ★ Active — H0 hackathon pivot (submit 2026-06-29 / judging ~7-24, submission plan docs/plans/2026-06-17-h0-submission.md, pivot docs/plans/2026-06-12-h0-hackathon.md, DECISIONS D5·D6·D7)
> Backend (store/worker/commands) + **web/ dashboard local complete**: Next.js App Router, jobs/detail
> (diff output gate + Approve/Reject)/metrics, DynamoDB Local offline docker (port 8930) — e2e verified.
> AWS credit request **rejected** → proceed with $63.91 on hand + free tier (inference is subscription OAuth = D6).
- [ ] `[manual]` DynamoDB table provision (`deploy/dynamodb/create-table.sh` — on-demand PAY_PER_REQUEST).
- [ ] `[manual]` Vercel deploy: web/ → connect real DynamoDB (`DDB_ENDPOINT` unset + read-key env, USER_GUIDE §5) → obtain Team ID/link.
- [ ] `[manual]` Real EC2 e2e once + capture numbers (diagnose N sec/$0.0X/M tool calls) → create real DynamoDB data.
- [ ] `[manual]` Submission: architecture diagram, DynamoDB screenshot, 3-min demo video, text description, Vercel link/Team ID, (bonus) article.
- [ ] `[manual]` After submission (6/29) EC2 stop, keep DynamoDB/Vercel (judging-period cost ~$0 — USER_GUIDE §7).

## Day 1–3 remaining — AWS/Slack execution (deploy/README.md order)
- [ ] `[manual]` Create Slack App (Socket Mode) + store SSM SecureString token + Claude subscription token (`claude setup-token`→SSM `/slackops/CLAUDE_CODE_OAUTH_TOKEN`, D6) — manual UI step.
- [ ] `[manual]` Run `deploy/iam/create-role.sh` — not run due to invalid local credentials.
- [ ] `[manual]` Run `deploy/ec2/launch-instance.sh` + replace user-data REPO_URL `CHANGE_ME`.
- [ ] `[manual]` Run `deploy/eventbridge/create-schedules.sh <instance-id>`.
- [ ] `[manual]` Confirm `/devops ping` end-to-end (Slack → EC2 → pong).
- [ ] `[manual]` Confirm **worker + chat_agent** resident live on EC2 — systemd units already wired in user-data.sh
      (3 services auto-register); after real boot just confirm 3 `systemctl status` active + web chat responds.

## Day 6–7 — tf-review + pr remaining
- [ ] `[manual]` GitHub App minimal scope + branch protection (block auto-merge) setup.

## Day 8–9 — Observability
- [ ] `[manual]` Configure ADOT Collector on EC2 + capture diagnose numbers once (N sec/$0.0X/M tool calls).

## Later — presentation/article (manual)
- [ ] `[manual]` Record demo + slides / AWSKRUG talk / PACE paragraph / article draft.
