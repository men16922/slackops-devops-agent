# NEXT_PLAN — slackops-devops-agent
Last updated: 2026-07-19

> **Open work only** (≤120 lines). Remove when done (history → PROGRESS_LOG/COMPLETED_SUMMARY). Authority: this file > docs/plans/.
> Tags: `[auto]` = doable in an unattended overnight round (local code+tests). `[manual]` = operator manual (AWS/Slack/UI).
> `[blocked]` = same item hit a Blocker twice — no unattended retry before human review (rounds append and skip).
> Unattended rounds do one `[auto]` top-to-bottom. Each item's "Done:" criterion must be met to finish.
> Completed history: docs/COMPLETED_SUMMARY.md (milestones) · docs/DECISIONS.md D19–D23 (secure-runtime rationale).

## ★ Active — v2 AWSKRUG 발표 데모
> 기능, Slack 승인, GitHub App PR #3–#5, 최종 18장 PDF/PPTX, 대본, LIVE 런북까지 완료했다.
- [ ] `[auto]` LIVE 자연어 diagnose scope 매핑을 고친다. Done: 문서의 exact sentence가 `resource_not_allowed` 없이
      read-only evidence 경로에 도달하고 회귀 TC가 통과한다.
- [ ] `[auto]` Slack terminal-state 동기화를 고친다. Done: FAILED/DONE 뒤 `analyzing`/`running now`가 사라지고
      실패 이유 또는 실제 PR 링크가 표시되는 TC와 실 Slack 확인이 있다.
- [ ] `[auto]` PR prepare 88초와 Plan C canned diff를 LIVE 기준에 맞춘다. Done: 40초 기준을 충족하거나 런북의
      전환 기준을 실측치로 조정하고, mock도 exact `DEFAULT_TIMEOUT_S 600→750` diff를 보여준다.
- [ ] `[manual]` Slide 4/6 페이지 번호 렌더링을 고치고 Slide 18 QR의 최종 목적지를 휴대폰으로 확인한다.
- [ ] `[manual]` 위 수정 후 `docs/presentation/LIVE.md` D-1 fresh-EC2 실경로를 재리허설하고 즉시 stop한다.
- [ ] `[manual]` 20분 발표 리허설: Slack diagnose → Review change → Approve → PR, A/B/C 전환까지 측정한다.
- [ ] `[manual]` 영문 V2 원고를 별도 Builder 글로 발행할지 결정한다. 기존 V1 글은 2026-07-17 현재 구현으로 갱신됨.
- [ ] `[manual]` Canvas 트라이얼 종료(~8/09) 전에 포스트모템 시연 화면을 최종 보관한다.

## Secure Agent Runtime — Notion 레퍼런스 잔여 (rationale: DECISIONS D19–D23)
> 레퍼런스 §8 Implementation Priority 의 **P0 전부 + P1 전부 닫힘**. **번호 체계가 repo 의
> P1/P2/P3(audit sink/scope boundary/managed-MCP pilot)와 다르다** — 섞어 쓰지 말 것.
- [x] **write credential 경로 검증** — 코드 correctness는 **TC로 검증 완료**(`make check` 542 passed:
      write_credentials/worker_write_grant/execution_plan/pr/worker/drift). 실 GitHub 발급→회수 로컬 스모크
      ✅(App `4313190`), SSM 4종 ✅, branch protection ✅. **선택 잔여** = 실 EC2 PR 1회(2클릭) — 배포
      #2/#3 선행. 상세: `docs/reports/2026-07-16-ec2-write-cred-rehearsal.md`.
- [x] **배포 안정화 #2/#3 — 코드+TC+실 EC2 검증 완료(2026-07-17)**. #2 refresh timer `OnBootSec` 45min→2min
      (실 부팅에서 boot+2m13s 발화, worker가 runtime-role로 DynamoDB claim→DONE). #3 `reclaim_stale_running`+
      `Worker.reclaim_stale()`(실 DynamoDB에서 고아 RUNNING→FAILED). user-data 16KB 한계 가드 추가. 상세:
      `docs/archive/progress-2026-07.md`의 2026-07-17 기록.
- [ ] `[auto]` P1 post-condition 확장(health/replica/config 재조회). **단 L2(Execute)가 비활성이라 검증할 실제 변경이
      없어 값어치가 낮다** — L2 를 열기 전에는 착수하지 말 것.
- [ ] `[manual]` P3 organization expansion pilot: managed AWS MCP 를 별도 role/context-key/CloudTrail 환경에서만 허용;
      선택 서버의 VPC endpoint 지원을 요건화하기 전에 확인. Done: 실제로 서로 다른 account ID, 승인된 pilot 전용
      trust policy, 빈 CloudTrail violation 쿼리가 generic MCP role 이 이 런타임에 닿지 않음을 증명한다.

## Day 1–3 — AWS/Slack execution (deploy/README.md order)
- [ ] `[manual]` `deploy/eventbridge/create-schedules.sh <id>` — skipped (terminate instead of schedule; revisit on redeploy).

## Day 8–9 — Observability
- [ ] `[manual]` Configure ADOT Collector on EC2 + capture diagnose numbers once (N sec/$0.0X/M tool calls).
