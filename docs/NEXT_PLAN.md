# NEXT_PLAN — slackops-devops-agent
Last updated: 2026-06-20

> **Open work only** (≤120 lines). Remove when done (history → PROGRESS_LOG/COMPLETED_SUMMARY). Authority: this file > docs/plans/.
> Tags: `[auto]` = doable in an unattended overnight round (local code+tests). `[manual]` = operator manual (AWS/Slack/UI).
> `[blocked]` = same item hit a Blocker twice — no unattended retry before human review (rounds append and skip).
> Unattended rounds do one `[auto]` top-to-bottom. Each item's "Done:" criterion must be met to finish.

## ★ Active — H0 submit (deadline **2026-06-30 09:00 GMT+9** / judging 7-01~7-25; plans: docs/submission/{schedule,final_submission,PRESENTATION}.md + docs/plans/2026-06-17-h0-submission.md, DECISIONS D5·D6·D7)
> **거의 완료.** 인프라(DynamoDB/EC2/Lambda+EventBridge/Vercel) · 기능(diagnose/승인게이트/이벤트구동 풀루프) · 캡처(DB screenshot/수치/링크·Team ID) 전부 live 검증.
> 현재 **비용 ≈ $0** (EC2 terminated, alarm 삭제). DynamoDB/Vercel/Lambda/SSM 유지. 남은 건 영상/텍스트/아티클 + 6/27 캡처세션.
- [x] 클라우드 배포 + **이벤트 구동 풀루프 live**(CloudWatch ALARM→EventBridge→Lambda→큐→worker→Slack, $0.15/run) · diagnose 실 CloudWatch · write-denied — 2026-06-20.
- [x] Vercel 배포 (link `slackops-devops-agent.vercel.app` + Team ID) · DynamoDB 증빙 스크린샷 · architecture diagram(+png).
- [ ] `[manual]` **6/27~28 캡처세션**: `make cloud-up`(SSM 5개 자동) → 영상 녹화(PRESENTATION slide 11 대본) → `make cloud-stop`.
- [ ] `[manual]` **3-min 데모영상** YouTube + `final_submission.md` *Video link* 기입.
- [ ] `[manual]` `final_submission.md` 텍스트 **본인 목소리 편집** (AI원문 제출 금지).
- [ ] `[manual]` (보너스) 아티클 + #H0Hackathon (6/30 전).
- [ ] `[manual]` **Devpost 제출**(6/27~28 권장) → 이후 EC2 stop 유지, 심사기간 DynamoDB/Vercel만(~$0). teardown=`schedule.md` §4.

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
