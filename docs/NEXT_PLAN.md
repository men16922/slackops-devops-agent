# NEXT_PLAN — slackops-devops-agent
Last updated: 2026-07-16

> **Open work only** (≤120 lines). Remove when done (history → PROGRESS_LOG/COMPLETED_SUMMARY). Authority: this file > docs/plans/.
> Tags: `[auto]` = doable in an unattended overnight round (local code+tests). `[manual]` = operator manual (AWS/Slack/UI).
> `[blocked]` = same item hit a Blocker twice — no unattended retry before human review (rounds append and skip).
> Unattended rounds do one `[auto]` top-to-bottom. Each item's "Done:" criterion must be met to finish.
> Completed history: docs/COMPLETED_SUMMARY.md (milestones) · docs/DECISIONS.md D19–D23 (secure-runtime rationale).

## ★ Active — v2 AWSKRUG 발표 데모
> D1–D4 + Modal/Shortcut 코드 완료, 실 Slack sandbox e2e 통과 (COMPLETED_SUMMARY 참조).
> 남은 것은 대부분 **사람이 클릭/등록/발표**해야 하는 항목이다.
> Slack은 새 워크스페이스("Platform Agent")로 이전 완료 — SSM Slack 4종 v2 갱신, 로컬 `/devops ping` pong 확인.
- [ ] `[manual]` AWSKRUG 슬라이드 디자인 마무리 (라이브 시연으로 대체, 사전 녹화 폐기).
      ⏰ Canvas 무료 트라이얼 **7/19 종료** — 캡처/데모는 그 전에.
- [ ] `[manual]` **새 워크스페이스**에 `review_slackops_job` Message Shortcut 등록 후 Modal diff 승인/거부 확인.
      Done: 비허용 사용자는 modal을 열거나 상태를 바꾸지 못하고, 허용 사용자의 결정은 원본 메시지와 감사 기록에 남음.
- [ ] `[manual]` EC2 리허설에서 `SLACK_APPROVER_IDS`(SSM v2 갱신됨)를 인스턴스 env에 반영하고 승인 버튼 검증.
      Done: 비허용 버튼 클릭은 거부되고, 허용 승인자는 감사 기록에 남음.

## Secure Agent Runtime — Notion 레퍼런스 잔여 (rationale: DECISIONS D19–D23)
> 레퍼런스 §8 Implementation Priority 의 **P0 전부 + P1 전부 닫힘**. **번호 체계가 repo 의
> P1/P2/P3(audit sink/scope boundary/managed-MCP pilot)와 다르다** — 섞어 쓰지 말 것.
- [x] **write credential 경로 검증** — 코드 correctness는 **TC로 검증 완료**(`make check` 542 passed:
      write_credentials/worker_write_grant/execution_plan/pr/worker/drift). 실 GitHub 발급→회수 로컬 스모크
      ✅(App `4313190`), SSM 4종 ✅, branch protection ✅. **선택 잔여** = 실 EC2 PR 1회(2클릭) — 배포
      #2/#3 선행. 상세: `docs/reports/2026-07-16-ec2-write-cred-rehearsal.md`.
- [~] **배포 안정화 #2** — credential refresher가 부팅 시 미가동(첫 발화 +43분) → 서비스가 초기 IAM 전파 지연으로
      DynamoDB Query 거부, worker claim 불가. **코드+테스트 완료(2026-07-17)**: refresh timer `OnBootSec` 45min→2min
      (부팅 직후 refresh+restart). 잔여 `[manual]` = 실 EC2 부팅에서 수렴 관측(선택). 상세: PROGRESS_LOG 2026-07-17.
- [~] **배포 안정화 #3** — 45분 credential 회전이 서비스 재시작으로 진행 중 worker job 을 끊어 고아 running 이
      되던 문제. **코드+TC 완료(2026-07-17, 551 passed)**: `reclaim_stale_running`(Sqlite/DynamoDb) +
      `Worker.reclaim_stale()`(startup·idle 회수, 타임아웃 초과 RUNNING→FAILED, 재큐 아님). 잔여 `[manual]` =
      실 EC2 리허설에서 회수 라이브 관측(선택). 상세: PROGRESS_LOG 2026-07-17.
- [ ] `[auto]` P1 post-condition 확장(health/replica/config 재조회). **단 L2(Execute)가 비활성이라 검증할 실제 변경이
      없어 값어치가 낮다** — L2 를 열기 전에는 착수하지 말 것.
- [ ] `[manual]` P3 organization expansion pilot: managed AWS MCP 를 별도 role/context-key/CloudTrail 환경에서만 허용;
      선택 서버의 VPC endpoint 지원을 요건화하기 전에 확인. Done: 실제로 서로 다른 account ID, 승인된 pilot 전용
      trust policy, 빈 CloudTrail violation 쿼리가 generic MCP role 이 이 런타임에 닿지 않음을 증명한다.

## Day 1–3 — AWS/Slack execution (deploy/README.md order)
- [ ] `[manual]` `deploy/eventbridge/create-schedules.sh <id>` — skipped (terminate instead of schedule; revisit on redeploy).

## Day 8–9 — Observability
- [ ] `[manual]` Configure ADOT Collector on EC2 + capture diagnose numbers once (N sec/$0.0X/M tool calls).

## Later — presentation/article (manual)
- [ ] `[manual]` Record demo + slides / AWSKRUG talk / PACE paragraph / article draft.
