# NEXT_PLAN — slackops-devops-agent
Last updated: 2026-06-20

> **Open work only** (≤120 lines). Remove when done (history → PROGRESS_LOG/COMPLETED_SUMMARY). Authority: this file > docs/plans/.
> Tags: `[auto]` = doable in an unattended overnight round (local code+tests). `[manual]` = operator manual (AWS/Slack/UI).
> `[blocked]` = same item hit a Blocker twice — no unattended retry before human review (rounds append and skip).
> Unattended rounds do one `[auto]` top-to-bottom. Each item's "Done:" criterion must be met to finish.

## ★ Active — v2 AWSKRUG 발표 데모 (plan: docs/plans/2026-06-25-awskrug-demo.md, branch `v2`)
> Slack 해커톤 제출은 **폐기**(Devpost §3 Eligibility 한국 미달 — plan 부록 §7). 목표 = AWSKRUG 라이브 데모.
> D1/D2/D2.5 **코드완료·게이트 green**(349 passed). 핵심 미완 = **실 Slack 검증**. 상세 단계는 plan §4.
- [x] D1 Assistant 핸들러 · D2 승인게이트(버튼↔출력게이트)+poll-in-thread · D2.5 포스트모템 Canvas(스파이크 통과) — 2026-06-26.
- [ ] `[manual]` **실 Slack sandbox e2e** — Assistant 스레드 자연어→제안→승인버튼→완료→Canvas. (현재 실 Slack 미검증)
- [ ] `[manual]` Modal diff 승인(`views.open`) · mrkdwn 렌더 · Message Shortcut(BUY 잔여).
- [ ] `[manual]` D3 로컬 mock 폴백(네트워크 없이 풀 시연 재현, `make demo` 에 Assistant 포함).
- [ ] `[manual]` D4 실 AWS 1회(`make cloud-up`→Assistant 실 CloudWatch 진단+write-denied→`cloud-stop`) + D2a(턴 내 AWS MCP read 스트리밍).
- [ ] `[manual]` D5/D6 사전 녹화 백업 + 인젝션 데모 1장면 + AWSKRUG 슬라이드.

## (폐기) H0 Devpost 제출 — 한국 자격 미달로 중단 (인프라/코드는 v2 가 재사용)
- [x] 클라우드 배포 + 이벤트구동 풀루프 live · Vercel 배포 · DynamoDB 증빙 — 2026-06-20 (자산은 유지, 비용 ≈ $0).

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
