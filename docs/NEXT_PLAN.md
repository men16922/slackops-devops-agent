# NEXT_PLAN — slackops-devops-agent
최종 갱신: 2026-06-11

> **열린 작업만** (≤120줄). 완료 시 제거(이력은 PROGRESS_LOG/COMPLETED_SUMMARY). 권위: 이 파일 > docs/plans/.

## Day 1–3 잔여 — AWS/Slack 실행분 (운영자 수동, deploy/README.md 순서)
- [ ] Slack App 생성(Socket Mode) + SSM SecureString 토큰 저장 — 근거: 수동 UI 단계, 코드로 불가.
- [ ] `deploy/iam/create-role.sh` 실행(IAM Role + Instance Profile) — 근거: 로컬 자격증명 무효로 미실행.
- [ ] `deploy/ec2/launch-instance.sh` 실행 + user-data 의 REPO_URL `CHANGE_ME` 교체 — 근거: GitHub remote 미정.
- [ ] `deploy/eventbridge/create-schedules.sh <instance-id>` 실행 — 근거: instance-id 필요.
- [ ] `/devops ping` end-to-end 확인(Slack → EC2 → pong) — 근거: A6 첫 명령, 현재 미검증.

## Day 4–5 — logs + diagnose + Sanitizer
- [ ] Context Sanitizer (`<untrusted_data>` 격리 주입) 구현 — 근거: 주입 방어 1계층.
- [ ] `/devops logs <service>` — CloudWatch 조회 + 분석 — 근거: A6.
- [ ] `/devops diagnose <service>` — CloudWatch + kubectl + git diff 종합 — 근거: A6.
- [ ] Permission Engine Level 0(Observe) 게이트 적용 — 근거: A3.
- [ ] Tool Allowlist(명령별 허용 도구) — 근거: 주입 방어 2계층.

## Day 6–7 — tf-review + pr + branch protection
- [ ] `/devops tf-review` — terraform plan 위험/비용/보안 리뷰 — 근거: A6.
- [ ] `/devops pr <설명>` — branch → 수정 → test → PR — 근거: A6, Level 1.
- [ ] 출력 게이트: PR diff Slack 스레드 선게시 + 사람 확인 — 근거: 주입 방어 3계층.
- [ ] GitHub App 최소 스코프 + branch protection(자동 머지 차단) — 근거: A2.

## Day 8–9 — OTel 계측 + 수치
- [ ] OTel SDK → ADOT Collector → CloudWatch 파이프라인 — 근거: A5.
- [ ] step latency / 토큰 / 비용(USD) / tool call / E2E p50·p95 계측 — 근거: A5.
- [ ] diagnose 1회 수치 캡처(N초/$0.0X/tool call M회) — 근거: A5 목표 수치.

## 이후 — 발표/아티클
- [ ] 데모 녹화(라이브 실패 대비 백업) + 슬라이드.
- [ ] AWSKRUG 영어 발표 + PACE 지원 문단 + 아티클 초안.
