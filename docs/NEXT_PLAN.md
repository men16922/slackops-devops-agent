# NEXT_PLAN — slackops-devops-agent
Last updated: 2026-07-15

> **Open work only** (≤120 lines). Remove when done (history → PROGRESS_LOG/COMPLETED_SUMMARY). Authority: this file > docs/plans/.
> Tags: `[auto]` = doable in an unattended overnight round (local code+tests). `[manual]` = operator manual (AWS/Slack/UI).
> `[blocked]` = same item hit a Blocker twice — no unattended retry before human review (rounds append and skip).
> Unattended rounds do one `[auto]` top-to-bottom. Each item's "Done:" criterion must be met to finish.

## ★ Active — v2 AWSKRUG 발표 데모 (plan: docs/plans/2026-06-25-awskrug-demo.md, branch `v2`)
> Slack 해커톤 제출은 **폐기**(Devpost §3 Eligibility 한국 미달 — plan 부록 §7). 목표 = AWSKRUG 라이브 데모.
> D1/D2/D2.5/D3 **코드완료·게이트 green**(358 passed). 핵심 미완 = **실 Slack 검증**(사람 타이핑). 상세 단계는 plan §4.
- [x] D1 Assistant 핸들러 · D2 승인게이트(버튼↔출력게이트)+poll-in-thread · D2.5 포스트모템 Canvas(스파이크 통과) — 2026-06-26.
- [x] D3 로컬 mock 폴백 — Assistant 콘솔(`make demo-assistant[-mock]`) real+오프라인 e2e + **인젝션 방어 장면 검증** — 2026-07-02.
- [x] **실 Slack sandbox e2e** — DM 폴백 경로로 6항목 전부 통과(스트리밍/버튼/approved 전이/Canvas/footer/payload) — 2026-07-02.
      ⏰ Canvas 는 무료 트라이얼 **7/19 종료** — 캡처/데모 그 전에.
- [ ] Modal diff 승인(`views.open`) · Message Shortcut — **미구현 BUY 잔여**(선택, mrkdwn 렌더는 검증됨).
- [x] `[manual]` D4 실 AWS 1회(EC2 start→`handle_diagnose` 실 CloudWatch 진단+write-denied 확인→EC2 stop) — 2026-07-06.
- [ ] `[manual]` AWSKRUG 슬라이드 디자인 마무리 (라이브 시연으로 대체, 사전 녹화 폐기).
- [ ] `[manual]` 다음 실 Slack/EC2 리허설에서 SSM에 동기화한 `SLACK_APPROVER_IDS`를 기존 인스턴스 환경 파일에 반영하고 승인 버튼 검증.
      Done: 비허용 버튼 클릭은 거부되고, 허용 승인자는 감사 기록에 남음.
## web 대시보드 UI 리디자인 후속 (branch `feature/dashboard-aws-theme`, 커밋 `35f4b38`)
- [ ] `[auto]` 시드 mock rationale 2개(agent-2001/2002, `web/scripts/seed.mjs`) 한글 → 영어 (H0 English UI / no-Korean-DOM 회복). Done: 재시드 후 Playwright 로 Proposal 컬럼 한글 미검출.

## (폐기) H0 Devpost 제출 — 한국 자격 미달로 중단 (인프라/코드는 v2 가 재사용)
- [x] 클라우드 배포 + 이벤트구동 풀루프 live · Vercel 배포 · DynamoDB 증빙 — 2026-06-20 (자산은 유지, 비용 ≈ $0).

## Day 1–3 — AWS/Slack execution (deploy/README.md order) — A–C DONE 2026-06-20
- [x] Slack App (Socket Mode) created + SSM SecureString tokens (bot/app/CLAUDE_CODE_OAUTH_TOKEN) stored.
- [x] `deploy/iam/create-role.sh` (role+profile, +AmazonSSMManagedInstanceCore for Session Manager).
- [x] `deploy/ec2/launch-instance.sh` (repo public-transitioned for unauth clone; 3 systemd services active) → `/devops ping` pong verified → EC2 terminated.
- [ ] `[manual]` `deploy/eventbridge/create-schedules.sh <id>` — skipped (terminate instead of schedule; revisit on redeploy).
- [ ] `[manual]` On redeploy: confirm 4 `systemctl status` active (slack/worker/chat-agent/monitor) + web chat responds.
- [ ] `[manual]` D17 split-role deployment: run `deploy/iam/create-role.sh`, launch a **new** EC2 (new user-data required),
      then verify 4 services + `slackops-runtime-credentials-refresh.timer`, runtime-role AWS read success, MCP proposal-queue
      write, and absence of direct service IMDS access. Stop the instance after evidence capture.

## Day 6–7 — tf-review + pr remaining
- [ ] `[manual]` GitHub App minimal scope + branch protection (block auto-merge) setup.

## Day 8–9 — Observability
- [ ] `[manual]` Configure ADOT Collector on EC2 + capture diagnose numbers once (N sec/$0.0X/M tool calls).

## Later — presentation/article (manual)
- [ ] `[manual]` Record demo + slides / AWSKRUG talk / PACE paragraph / article draft.
