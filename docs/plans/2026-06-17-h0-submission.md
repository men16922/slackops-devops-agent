# H0 제출 플랜 (현행) — slackops-devops-agent

최종 갱신: 2026-06-20 · 마감 **2026-06-29** · 심사 6/30~7/24
근거: H0 Requirements(Track 2 B2B) + Devpost 채점 메일(메모리 [[h0-judging-guidance]]).

> **상태: 인프라·기능·배포·캡처 = 완료.** 남은 건 **제출 아티팩트 3개**(다이어그램/텍스트/영상)뿐.
> 채점은 앱 직접 테스트보다 **영상 + 설명 + 아키텍처 표현** 비중이 큼 → 남은 시간은 거기 투자.

---

## ✅ 완료 (live 검증)

**인프라/배포**
- DynamoDB `slackops-agent` us-east-1 — ACTIVE / PAY_PER_REQUEST / GSI1·GSI2
- EC2(t3.medium) + systemd 4개: slack(app.main) / worker / chat-agent / monitor — `make cloud-up`
- Vercel 대시보드 배포 — 실 DynamoDB 연결, 라이브 정상 기동
- 이벤트 구동 producer 배포 — EventBridge rule + Lambda (`make cloud-lambda-deploy`)
- Slack 생명주기 알림 활성화 — `SLACK_NOTIFY_CHANNEL` (채널 `C0BC0PFLP8U`)

**기능 (실 Claude·실 AWS e2e)**
- `/devops ping|diagnose` — 실 CloudWatch(Instance Profile, AWS API MCP, read-only) 진단, 영어 출력
- write op → "denied by security policy" (read-only 경계 증명)
- 자율 제안 → 사람 승인 게이트(출력 게이트, optimistic-lock)
- **이벤트 구동 풀루프**: CloudWatch ALARM → EventBridge → Lambda(detect) → DynamoDB 큐 →
  worker(claude -p) → DONE → Slack 알림 — `make cloud-alarm` 으로 실시간 검증

**캡처**
- DynamoDB 증빙 스크린샷: `docs/submission/items.png`(단일테이블 JOB#/META/AUDIT#/METRIC# + 실 비용) · `docs/submission/tables.png`
- 수치(실측): diagnose 1회 **~$0.15 / 2.7K~6K tok** (Slack done 알림 기준)

---

## ⏳ 남은 제출 작업 (3개 + 보너스)

- [ ] **아키텍처 다이어그램** — Mermaid→PNG. 반드시 포함: Slack+Vercel 이 **하나의 DynamoDB single-table 큐** 공유 →
      EC2 worker(Claude/도구) → 결과. **이벤트 구동 경로**(CloudWatch ALARM→EventBridge→Lambda→큐). 권한 L0/1 + 주입방어 4계층 + OTel.
      *(작업 가능: `docs/submission/architecture.md` 갱신)*
- [ ] **텍스트 설명** — 무엇/누구/왜 + "AWS Database used: **DynamoDB**". 보안(권한+주입방어)·관측(OTel)·**이벤트 구동 자율 감지** 차별화.
      DEVPOST 초안(`docs/guide/{en,kr}/DEVPOST.md`) → **본인 목소리로 편집(필수)**.
- [ ] **데모영상 <3분(YouTube)** — 아래 §영상순서. README 낭독 금지.
- [ ] **(보너스 +0.6)** 공개 아티클(dev.to/medium/LinkedIn) + 해커톤 목적 + **#H0Hackathon**, 6/29 전 발행.

---

## 확보된 제출 아티팩트

| 항목 | 값 |
| --- | --- |
| Published Vercel Link | https://slackops-devops-agent.vercel.app/ |
| Vercel Team ID | `team_Exh42D0O6q3f4xJA4j8lbv2P` |
| DynamoDB 증빙 | `docs/submission/items.png` (+ `tables.png`) |
| 실측 수치 | diagnose ~$0.15 / 2.7K~6K tok |

---

## DB 정당화 한 문장 (텍스트·영상에 그대로)

> Slack 과 Vercel 두 control plane 이 하나의 작업 큐를 공유 → **DynamoDB conditional write** 로
> 별도 코디네이터 없이 atomic job claim + optimistic-lock 승인 게이트 구현. 게다가 **EventBridge→Lambda**
> 이벤트 producer 가 같은 single-table 에 제안을 적재 → 사람·에이전트·이벤트가 한 큐를 공유. (Aurora 아닌 DynamoDB 인 이유)

---

## 데모 영상 순서 (<3분)

1. **문제/대상** (20s) — 운영 장애 대응을 Slack 한 줄로, 안전하게(읽기전용+승인게이트).
2. **Slack diagnose** (40s) — `/devops diagnose checkout-service` → 실 CloudWatch 진단 + write-denied.
3. **이벤트 구동 자율 감지** (40s) — `make cloud-alarm` → alarm → EventBridge→Lambda → Slack 제안 알림(실시간).
4. **승인 게이트** (30s) — Vercel 대시보드에서 제안 확인 → Approve → 실행 → done($0.15).
5. **DB 통합 설명** (20s) — items.png + DB 정당화 한 문장.
6. (마무리) 보안 4계층 + OTel 한 줄.

---

## 제출 직전 / 후

- [ ] 미푸시 커밋 push (`git push origin main`) → Vercel 자동 재배포.
- [ ] 캡처/영상 완료 후 **비용 정리**: `make cloud-stop`(또는 `cloud-down`) · `make cloud-alarm-clean` · `make cloud-lambda-clean`.
- [ ] 심사기간 유지: DynamoDB(온디맨드)·Vercel(Hobby)·키 — idle ~$0. EC2 만 stop.
- [ ] 불변 유지: Production 변경/IAM·DB 변경/Level 2/인바운드 포트 없음.
