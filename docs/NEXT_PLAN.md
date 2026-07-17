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
      ⏰ Canvas 무료 트라이얼 **~8/09 종료**(새 워크스페이스로 교체돼 트라이얼 갱신, 2026-07-17 기준 23일) — 그 전에 캡처/데모.
- [~] `review_slackops_job` Message Shortcut — **등록 확인 완료(2026-07-17)**: 앱 config(Interactivity On,
      callback_id `review_slackops_job`, Messages) + Slack 메시지 "More actions"에 "Review SlackOps job" 노출 확인.
      **미완**: shortcut 호출 시 Modal이 안 열림. 메시지는 `decision_blocks`로 `approval:{job_id}` 블록을 정상 렌더하나
      `_on_shortcut`이 로그가 없어 발화/실패를 확인 불가. 유력 가설 = **Assistant DM 스레드** 메시지의 shortcut 페이로드가
      custom blocks 미포함 → `job_id_from_message_blocks`=None. 후속: ① `_on_shortcut`에 log 추가(진단 가능성 확보 —
      app structlog가 journald 에 안 남는 문제도 같이) ② **채널 알림 메시지**(proposal_notifier)에서 재검증.
      Done 기준: 비허용자는 상태를 못 바꾸고(제출 시 NOT_AUTHORIZED), 허용자의 결정은 원본 메시지+감사에 남음.
- [x] **승인자 검증 완료(2026-07-17)** — `SLACK_APPROVER_IDS` SecureString 미복호화 버그 수정(`63ec156`);
      men16922 가 대시보드에서 승인 성공, 감사 `approved` 기록. (Slack Message Shortcut 등록은 위 항목 참조 — 대시보드 경로는 검증됨.)
- [x] **pr execute-blocking 버그 FIXED + 실 PR 라이브 검증 완료(2026-07-17)** — 3중 근본원인 스택 해결:
      ① diff-source 정본화(`ba813bf`, `current_workspace_diff`) ② execute git 배관을 런타임 결정적으로
      (`9081bed`, `app.pr_execution.open_pr` — LLM 제거) ③ postcondition gh 인증을 grant 환경으로 이동
      (`be0422d`). job `f879c3fe`=DONE, **GitHub PR #3 OPEN**. `make check` 563 passed. 상세: PROGRESS_LOG 2026-07-17.
      잔여: 테스트 PR #2/#3(unmerged) 닫기.

## Secure Agent Runtime — Notion 레퍼런스 잔여 (rationale: DECISIONS D19–D23)
> 레퍼런스 §8 Implementation Priority 의 **P0 전부 + P1 전부 닫힘**. **번호 체계가 repo 의
> P1/P2/P3(audit sink/scope boundary/managed-MCP pilot)와 다르다** — 섞어 쓰지 말 것.
- [x] **write credential 경로 검증** — 코드 correctness는 **TC로 검증 완료**(`make check` 542 passed:
      write_credentials/worker_write_grant/execution_plan/pr/worker/drift). 실 GitHub 발급→회수 로컬 스모크
      ✅(App `4313190`), SSM 4종 ✅, branch protection ✅. **선택 잔여** = 실 EC2 PR 1회(2클릭) — 배포
      #2/#3 선행. 상세: `docs/reports/2026-07-16-ec2-write-cred-rehearsal.md`.
- [x] **배포 안정화 #2/#3 — 코드+TC+실 EC2 검증 완료(2026-07-17)**. #2 refresh timer `OnBootSec` 45min→2min
      (실 부팅에서 boot+2m13s 발화, worker가 runtime-role로 DynamoDB claim→DONE). #3 `reclaim_stale_running`+
      `Worker.reclaim_stale()`(실 DynamoDB에서 고아 RUNNING→FAILED). user-data 16KB 한계 가드 추가. 상세: PROGRESS_LOG 2026-07-17.
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
