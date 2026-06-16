# NEXT_PLAN — slackops-devops-agent
최종 갱신: 2026-06-16

> **열린 작업만** (≤120줄). 완료 시 제거(이력은 PROGRESS_LOG/COMPLETED_SUMMARY). 권위: 이 파일 > docs/plans/.
> 태그: `[auto]` = overnight 무인 회차 수행 가능(로컬 코드+테스트). `[manual]` = 운영자 수동(AWS/Slack/UI).
> `[blocked]` = 같은 항목 Blocker 2회 누적 — 사람 검수 전 무인 재시도 금지(회차가 덧붙이고 건너뜀).
> 무인 회차는 위에서 아래로 `[auto]` 1개씩 수행. 각 항목의 "완료:" 기준을 충족해야 종료.

## ★ Active — H0 해커톤 피벗 (제출 2026-06-29 / 심사 ~7-24, 상세 docs/plans/2026-06-12-h0-hackathon.md, DECISIONS D5·D6·D7)
> 백엔드(store/worker/commands) + **web/ 대시보드 로컬 완성**: Next.js App Router, jobs/상세
> (diff 출력게이트+Approve/Reject)/metrics, DynamoDB Local 오프라인 docker(포트 8930) — e2e 검증.
> AWS 크레딧 신청은 **거절** → 보유 $63.91 + 무료티어로 진행(추론은 구독 OAuth=D6).
- [ ] `[manual]` DynamoDB 테이블 provision(`deploy/dynamodb/create-table.sh` — 온디맨드 PAY_PER_REQUEST).
- [ ] `[manual]` Vercel 배포: web/ → 실 DynamoDB 연결(`DDB_ENDPOINT` 미설정 + 읽기키 env, USER_GUIDE §5) → Team ID/링크 확보.
- [ ] `[manual]` 실 EC2 e2e 1회 + 수치 캡처(diagnose N초/$0.0X/tool call M회) → DynamoDB 실데이터 생성.
- [ ] `[manual]` 제출물: 아키텍처 다이어그램·DynamoDB 스크린샷·3분 데모영상·텍스트설명·Vercel 링크/Team ID·(보너스)아티클.
- [ ] `[manual]` 제출(6/29) 후 EC2 stop, DynamoDB/Vercel 유지(심사기간 비용 ~$0 — USER_GUIDE §7).

## Day 1–3 잔여 — AWS/Slack 실행분 (deploy/README.md 순서)
- [ ] `[manual]` Slack App 생성(Socket Mode) + SSM SecureString 토큰 저장 + Claude 구독 토큰(`claude setup-token`→SSM `/slackops/CLAUDE_CODE_OAUTH_TOKEN`, D6) — 수동 UI 단계.
- [ ] `[manual]` `deploy/iam/create-role.sh` 실행 — 로컬 자격증명 무효로 미실행.
- [ ] `[manual]` `deploy/ec2/launch-instance.sh` 실행 + user-data REPO_URL `CHANGE_ME` 교체.
- [ ] `[manual]` `deploy/eventbridge/create-schedules.sh <instance-id>` 실행.
- [ ] `[manual]` `/devops ping` end-to-end 확인(Slack → EC2 → pong).

## Day 6–7 — tf-review + pr 잔여
- [ ] `[manual]` GitHub App 최소 스코프 + branch protection(자동 머지 차단) 설정.

## Day 8–9 — Observability
- [ ] `[manual]` EC2 에 ADOT Collector 구성 + diagnose 1회 수치 캡처(N초/$0.0X/tool call M회).

## 이후 — 발표/아티클 (manual)
- [ ] `[manual]` 데모 녹화 + 슬라이드 / AWSKRUG 발표 / PACE 문단 / 아티클 초안.
