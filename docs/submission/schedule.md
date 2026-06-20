# 제출 · 심사 기간 계획 (비용/운영)

> **현재(2026-06-20): EC2 terminated · 데모 alarm 삭제 → 비용 ≈ $0.** DynamoDB/Vercel/Lambda/EventBridge 유지(idle ~$0).
> **타깃: 6/27~28 최종 작업 1세션** — EC2 재기동(`make cloud-up`, 최신 코드) → 영상 캡처 → 즉시 stop → Devpost 제출(마감 6/30 09:00).
> 재기동 후 이벤트 경로 점검: 이미 배포된 Lambda/rule 그대로 → `make cloud-alarm` 만 다시 돌리면 됨(alarm 재생성 포함).

| Period | Begins (GMT+9) | Ends (GMT+9) |
| --- | --- | --- |
| **Submissions** | May 28 04:00 | **Jun 30 09:00** |
| **Judging** | Jul 01 01:00 | Jul 25 09:00 |
| **Winners** | — | Aug 01 06:00 |

> 핵심: **유일한 실질 비용 = EC2(~$1/day).** DynamoDB(온디맨드)·Vercel(Hobby)·Lambda/EventBridge(무료티어)는 idle ~$0.
> 따라서 비용절감 = "EC2는 캡처할 때만 켜고 즉시 stop". 제출 시점 자체는 비용과 무관(폼 제출은 무료).

---

## 1) 제출 전 — 캡처/녹화 (집중 1세션, EC2 비용 최소화)

EC2 켜진 동안 **한 번에** 모든 라이브 footage 를 캡처 → 끝나면 즉시 stop.
- [ ] EC2 up (이미 running) — 캡처 끝날 때까지만 유지
- [ ] 녹화: Slack `diagnose` · write-denied · `make cloud-alarm`(이벤트 구동 풀루프) · 대시보드 승인
- [ ] DynamoDB 콘솔 스크린샷(이미 `items.png`)
- [ ] **캡처 직후** `make cloud-stop` (또는 `cloud-down`) ← 비용 정지
- 예상 비용: 캡처 수 시간 = **$1 미만**

## 2) 제출 (Devpost)

- **권장 제출일: 6/28~6/29** (마감 6/30 09:00 이지만 **1일 버퍼** — 막판 기술이슈 방지). "마지막날 아슬아슬"은 리스크.
- 제출에 EC2 불필요 → 캡처/녹화 끝났으면 EC2는 stop 상태로 제출해도 됨.
- 제출물: `final_submission.md`의 각 필드 + 영상 링크 + `architecture.png` + `items.png` + Vercel 링크/Team ID.
- (보너스) 아티클 6/29 전 발행 + #H0Hackathon.

## 3) 심사 기간 (7/01~7/25) — EC2 OFF 유지

심사는 **영상 + 설명 + 라이브 대시보드** 중심. 라이브 Slack 에이전트는 기본 불필요.
- **유지(필수, ~$0):**
  - Vercel 대시보드 — 심사관이 링크 클릭 → 살아있어야 함 (Hobby 무료)
  - DynamoDB `slackops-agent` — 대시보드가 읽음. 실데이터 그대로 유지(빈 화면 방지)
  - Vercel IAM 키 — 대시보드 읽기용
- **정지(비용 절감):**
  - **EC2 stop** — 심사 내내 OFF. 라이브 Slack 데모 요청 시 `make cloud-up`(~5분)으로 즉시 부활
- **정리(선택):**
  - 데모 alarm: `make cloud-alarm-clean` (~$0.10/mo, 정리 권장)
  - Lambda/EventBridge: 무료티어라 둬도 무방. 라이브 테스트 대비 유지 권장(`make cloud-lambda-clean`로 언제든 정리)
- **심사기간 총비용 ≈ $0** (DynamoDB idle + Vercel 무료)

### 심사관 테스트 안내 (Devpost "Testing Instructions")
> 라이브 대시보드: <Vercel 링크> — 실 DynamoDB 데이터(diagnose Job/Audit/Metric)가 그대로 보임.
> Slack 에이전트 라이브 데모가 필요하면 요청 주세요(EC2 on-demand 기동, ~5분). 비용 절감을 위해 평시 EC2 는 정지.

## 4) 수상 발표 후 (8/01~) — 전체 정리

- [ ] `make cloud-down` (EC2 terminate) · `make cloud-lambda-clean` · `make cloud-alarm-clean` · `make cloud-vercel-key-clean`
- [ ] (선택) DynamoDB 테이블 삭제 / Vercel 프로젝트 보존 여부 결정
- [ ] 노출됐던 IAM 키 비활성화 확인

---

## 비용 요약 (us-east-1)

| 리소스 | 캡처 중 | 심사기간(EC2 off) |
| --- | --- | --- |
| EC2 t3.medium | ~$0.04/h (몇 시간) | **$0 (stop)** |
| DynamoDB 온디맨드 | ~$0 (idle) | ~$0 |
| Vercel Hobby | $0 | $0 |
| Lambda + EventBridge | $0 (무료티어) | $0 |
| 데모 alarm | ~$0.003/일 | 정리 시 $0 |
| **합계** | **< $1** | **≈ $0** |
