# NEXT_PLAN — slackops-devops-agent
최종 갱신: 2026-06-13

> **열린 작업만** (≤120줄). 완료 시 제거(이력은 PROGRESS_LOG/COMPLETED_SUMMARY). 권위: 이 파일 > docs/plans/.
> 태그: `[auto]` = overnight 무인 회차 수행 가능(로컬 코드+테스트). `[manual]` = 운영자 수동(AWS/Slack/UI).
> `[blocked]` = 같은 항목 Blocker 2회 누적 — 사람 검수 전 무인 재시도 금지(회차가 덧붙이고 건너뜀).
> 무인 회차는 위에서 아래로 `[auto]` 1개씩 수행. 각 항목의 "완료:" 기준을 충족해야 종료.

## ★ Active — H0 해커톤 피벗 (마감 2026-06-30, 상세 docs/plans/2026-06-12-h0-hackathon.md, DECISIONS D5)
> store/ + worker + commands 전부 완료: JobStore/AuditStore/TelemetryStore(단일테이블) +
> Worker 폴링 루프 + commands/{tf_review,pr}(pr 출력게이트 = CommandOutcome.diff 연결).
> 로컬 [auto] 잔여는 Day 8–9 Observability 뿐.
- [ ] `[manual]` v0 로 web/ Next.js 대시보드 스캐폴드 → server actions↔DynamoDB → Vercel 배포.
- [ ] `[manual]` AWS/v0 크레딧 신청 + DynamoDB 테이블 provision + 실 EC2 e2e 1회 캡처.
- [ ] `[manual]` 제출물: 아키텍처 다이어그램·DynamoDB 스크린샷·3분 데모영상·텍스트설명·Vercel 링크/Team ID·(보너스)아티클.

## Day 1–3 잔여 — AWS/Slack 실행분 (deploy/README.md 순서)
- [ ] `[manual]` Slack App 생성(Socket Mode) + SSM SecureString 토큰 저장 — 수동 UI 단계.
- [ ] `[manual]` `deploy/iam/create-role.sh` 실행 — 로컬 자격증명 무효로 미실행.
- [ ] `[manual]` `deploy/ec2/launch-instance.sh` 실행 + user-data REPO_URL `CHANGE_ME` 교체.
- [ ] `[manual]` `deploy/eventbridge/create-schedules.sh <instance-id>` 실행.
- [ ] `[manual]` `/devops ping` end-to-end 확인(Slack → EC2 → pong).

## Day 6–7 — tf-review + pr 잔여
- [ ] `[manual]` GitHub App 최소 스코프 + branch protection(자동 머지 차단) 설정.

## Day 8–9 — Observability
- [ ] `[auto]` claude_runner·commands 에 telemetry 계측 결합 — 완료: 호출 시 지표 기록 테스트 green.
- [ ] `[manual]` EC2 에 ADOT Collector 구성 + diagnose 1회 수치 캡처(N초/$0.0X/tool call M회).

## Day 9.5 — 품질 리뷰 회차 (구현 체인 뒤 read-only 검증 단계)
- [ ] `[auto]` 리뷰 회차 — H0 milestone 커밋 range(store~Observability)를 보안(주입 방어 우회)/
      타입/단순화 관점으로 **read-only 리뷰**. 코드 수정 금지 — findings 는 이 파일에 `[auto]`
      항목으로 환류 + PROGRESS_LOG 기록. 완료: findings 환류 또는 'clean' 기록.

## 이후 — 발표/아티클 (manual)
- [ ] `[manual]` 데모 녹화 + 슬라이드 / AWSKRUG 발표 / PACE 문단 / 아티클 초안.
