# NEXT_PLAN — slackops-devops-agent
최종 갱신: 2026-06-12

> **열린 작업만** (≤120줄). 완료 시 제거(이력은 PROGRESS_LOG/COMPLETED_SUMMARY). 권위: 이 파일 > docs/plans/.
> 태그: `[auto]` = overnight 무인 회차 수행 가능(로컬 코드+테스트). `[manual]` = 운영자 수동(AWS/Slack/UI).
> 무인 회차는 위에서 아래로 `[auto]` 1개씩 수행. 각 항목의 "완료:" 기준을 충족해야 종료.

## Day 1–3 잔여 — AWS/Slack 실행분 (deploy/README.md 순서)
- [ ] `[manual]` Slack App 생성(Socket Mode) + SSM SecureString 토큰 저장 — 수동 UI 단계.
- [ ] `[manual]` `deploy/iam/create-role.sh` 실행 — 로컬 자격증명 무효로 미실행.
- [ ] `[manual]` `deploy/ec2/launch-instance.sh` 실행 + user-data REPO_URL `CHANGE_ME` 교체.
- [ ] `[manual]` `deploy/eventbridge/create-schedules.sh <instance-id>` 실행.
- [ ] `[manual]` `/devops ping` end-to-end 확인(Slack → EC2 → pong).

## Day 6–7 — tf-review + pr
- [ ] `[auto]` `commands/tf_review.py` 구현 — terraform plan 실행기 주입(mock), plan 출력 격리
      → 위험/비용/보안 리뷰 프롬프트. 완료: mock 테스트 green, apply 경로 부재 확인 테스트.
- [ ] `[auto]` `commands/pr.py` 구현 — branch→수정→test→PR 단계 조립(gh 실행기 주입 mock) +
      출력 게이트(diff 선게시 후 확인 토큰 필요 구조). 완료: 게이트 없이 PR 생성 불가 테스트 green.
- [ ] `[manual]` GitHub App 최소 스코프 + branch protection(자동 머지 차단) 설정.

## Day 8–9 — Observability
- [ ] `[auto]` `telemetry.py` 구현 — OTel SDK 셋업(lazy import) + record_run_metrics
      (step latency/토큰/비용/tool call/실패). 완료: in-memory exporter 또는 mock 테스트 green.
- [ ] `[auto]` claude_runner·commands 에 telemetry 계측 결합 — 완료: 호출 시 지표 기록 테스트 green.
- [ ] `[manual]` EC2 에 ADOT Collector 구성 + diagnose 1회 수치 캡처(N초/$0.0X/tool call M회).

## 이후 — 발표/아티클 (manual)
- [ ] `[manual]` 데모 녹화 + 슬라이드 / AWSKRUG 발표 / PACE 문단 / 아티클 초안.
