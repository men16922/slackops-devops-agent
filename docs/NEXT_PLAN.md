# NEXT_PLAN — slackops-devops-agent
최종 갱신: 2026-06-11

> **열린 작업만** (≤120줄). 완료 시 제거(이력은 PROGRESS_LOG/COMPLETED_SUMMARY). 권위: 이 파일 > docs/plans/.

## Day 1–3 — 기반 + ping
- [ ] EC2(c7i.large) 프로비저닝 + IAM Instance Profile(읽기 전용 정책) — 근거: A2/A8, Access Key 금지.
- [ ] EC2 에 Claude Code Headless + AWS CLI/kubectl/terraform/gh/helm/jq 설치 — 근거: A2 도구 체인.
- [ ] Slack App 생성(Socket Mode, App/Bot 토큰) — 근거: 인바운드 포트 없음.
- [ ] `slack_handler` Socket Mode client 연결 + 명령 라우팅 — 근거: src/app 레이어.
- [ ] `/devops ping` 헬스체크 end-to-end 동작 — 근거: A6 첫 명령.
- [ ] EventBridge 스케줄 stop/start 구성 — 근거: A4 비용/상시 금지.

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
