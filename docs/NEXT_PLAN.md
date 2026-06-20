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
- [x] **F1–F5 + Slack(`/devops detect`+생명주기 알림) + `make cloud-alarm` 로컬 e2e 라이브 검증** 2026-06-20 (gate 310 green).
- [ ] **Phase 3-deploy(클라우드 캡처)** — relaunch EC2 (t3.medium; systemd 4개: slack/worker/chat-agent/**monitor**) → 캡처 체크리스트
      **`docs/test/0620-qa-test.md`**: `/devops diagnose|detect`(실 findings) · write-denied · `make cloud-alarm` · DynamoDB screenshot. EC2 currently terminated.
- [ ] `[manual]` Vercel deploy: web/ → connect real DynamoDB (`DDB_ENDPOINT` unset + read-key env, DASHBOARD_GUIDE §7) → obtain Team ID/link.
- [ ] `[manual]` Capture numbers (diagnose N sec/$0.0X/M tool calls) + real DynamoDB data (on redeploy).
- [ ] `[manual]` Submission: architecture diagram, DynamoDB screenshot, 3-min demo video, text description, Vercel link/Team ID, (bonus) article.
- [ ] `[manual]` After submission (6/29) EC2 stop, keep DynamoDB/Vercel (judging-period cost ~$0 — SLACK_GUIDE §5).

## Day 1–3 — AWS/Slack execution (deploy/README.md order) — A–C DONE 2026-06-20
- [x] Slack App (Socket Mode) created + SSM SecureString tokens (bot/app/CLAUDE_CODE_OAUTH_TOKEN) stored.
- [x] `deploy/iam/create-role.sh` (role+profile, +AmazonSSMManagedInstanceCore for Session Manager).
- [x] `deploy/ec2/launch-instance.sh` (repo public-transitioned for unauth clone; 3 systemd services active) → `/devops ping` pong verified → EC2 terminated.
- [ ] `[manual]` `deploy/eventbridge/create-schedules.sh <id>` — skipped (terminate instead of schedule; revisit on redeploy).
- [ ] `[manual]` On redeploy: confirm 4 `systemctl status` active (slack/worker/chat-agent/monitor) + web chat responds.

## Day 6–7 — tf-review + pr remaining
- [ ] `[manual]` GitHub App minimal scope + branch protection (block auto-merge) setup.

## Day 8–9 — Observability
- [ ] `[manual]` Configure ADOT Collector on EC2 + capture diagnose numbers once (N sec/$0.0X/M tool calls).

## Later — presentation/article (manual)
- [ ] `[manual]` Record demo + slides / AWSKRUG talk / PACE paragraph / article draft.
