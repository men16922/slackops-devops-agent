# Plan Snapshot — H0 Hackathon 피벗 (2026-06-12)

> historical 스냅샷. 권위는 docs/NEXT_PLAN.md. 상세 설계는 이 문서 + DECISIONS D5.

## 정체성
H0 해커톤("Hack the Zero Stack with Vercel v0 + AWS Databases", 마감 2026-06-30 09:00 KST).
컨셉: **One Agent, Two Control Planes** — 사무실=Vercel/Next.js 대시보드, 원격=Slack, 둘 다
**DynamoDB 공유 job queue**로 같은 EC2 에이전트 백엔드 구동. Track 2(B2B). AWS DB = DynamoDB.

## 아키텍처
```
Vercel Next.js (server actions, AWS SDK v3) ─┐
Slack (Socket Mode, EC2, boto3) ─────────────┴─→ DynamoDB(single-table: jobs·audit·telemetry)
                                                   ▲ poll(GSI)/write-back
                            EC2 Agent Worker(Claude Code Headless: 권한·sanitizer·allowlist·OTel)
```

## DynamoDB 단일테이블 (`slackops-agent`)
| 항목 | PK | SK | GSI1 | GSI2 |
|---|---|---|---|---|
| Job | `JOB#{id}` | `META` | `STATUS#{status}`/`{createdAt}` | `FEED`/`{createdAt}` |
| Audit | `JOB#{id}` | `AUDIT#{ts}#{seq}` | — | `AUDIT#{yyyymmdd}`/`{ts}` |
| Metric | `JOB#{id}` | `METRIC#{ts}` | — | `METRIC#{yyyymmdd}`/`{ts}` |

상태머신: PENDING → (L1 쓰기면) AWAITING_APPROVAL → APPROVED → RUNNING → DONE|FAILED.
claim = Query GSI1(STATUS#PENDING) → UpdateItem ConditionExpression(optimistic lock) — SQLite RETURNING 대체.

## 18일 계획 요약
D1 셋업/문서/DynamoDB provision · D2–4 store 데이터층(moto) · D4–6 worker 루프 · D6–10 v0 프론트+Vercel ·
D10–13 출력게이트+계측 · D13–15 실 인프라 e2e 캡처 · D15–17 제출물(영상/다이어그램/스크린샷) · D17–18 버퍼.
Stretch B 게이트 = D8.

## 재사용
permissions / sanitizer / claude_runner / allowlist / commands(ping·logs·diagnose) 그대로.
신규: store/ · worker.py · web/(Next.js) · commands/{tf_review,pr} · telemetry 구현 · deploy DynamoDB.

## 제출물
텍스트 설명(DB=DynamoDB) · 3분 데모영상 · Vercel 링크+Team ID · 아키텍처 다이어그램 · DynamoDB 스크린샷
· (보너스) #H0Hackathon 아티클.
