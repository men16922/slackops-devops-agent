# QA TEST — 2026-06-20 로컬 e2e (F1–F5 알림 루프 + 거버넌스 Detections)

> 대상: F1–F5(상주 모니터·Slack/대시보드 알림·거버넌스 detect·Detections 메뉴) 로컬 검증.
> 환경: `web/docker-compose`(web 8930 + DynamoDB Local 8931, **Claude 토큰·AWS 자격증명 불필요**). seed = `web/scripts/seed.mjs`(탐지 토글 4종 포함).
> 자동 게이트(별도): `make check` **307 passed** · ruff · mypy(31) · doc-budget / web `next build` green.

---

## A. Playwright 직접 검증 — ✅ 통과 (이 세션)

| # | 검증 | 결과 | 근거 |
| --- | --- | --- | --- |
| 1 | 대시보드 렌더 + nav | ✅ | `localhost:8930` Jobs/Detections/Metrics nav, 시드 큐 렌더, 콘솔 에러 = favicon 404 뿐(무해) |
| 2 | 🔔 알림 벨 unread | ✅ | 시드 agent 제안 2건 → 벨 배지 **"2"** |
| 3 | 벨 드롭다운 | ✅ | `diagnose api` + `pr bump nginx…` 가 명령·args·**rationale**·`/jobs/agent-200x` 링크로 표시 |
| 4 | Mark all seen | ✅ | 클릭 후 배지 "2" 사라짐(워터마크 갱신) |
| 5 | Detections 메뉴 | ✅ | 3그룹(Security/Operations/Cost). 시드 반영: **IAM=ON·Scheduled, Config=ON·On-demand**, SSM/CloudWatch=OFF, Trusted Advisor/Security Hub/GuardDuty=**roadmap(비활성)** |
| 6 | **Scan now → 작업 적재** | ✅ | Config "Scan now" → 큐 최상단에 **`pending · detect · config · web`** 등장 |
| 7 | 작업 상세 + 출력 게이트 | ✅ | `/jobs/pr-1001` diff 미리보기 + Approve/Reject + Audit Timeline |
| 8 | **승인 전이** | ✅ | Approve → 상태 **approved**, "Approved by: web-operator @ …", Audit 에 `approved · via web dashboard` append |

스크린샷/스냅샷: `.playwright-mcp/` (세션 산출물).

---

## B. 운영자(당신) 검증 — 미결 (실 Claude 토큰 / Slack / 클라우드 필요)

| # | 검증 | 방법 |
| --- | --- | --- |
| B1 | 대화형 채팅 스트리밍 | `make demo` 풀스택 → 채팅 입력 → `chat_agent` 스트리밍 응답(Markdown) |
| B2 | worker 실제 실행 | 승인분 `make worker ARGS=--once` → done + 비용/토큰 (로컬 diagnose=git diff 폴백) |
| B3 | **Scan now 실제 findings** | 위 6번 detect 작업을 worker 가 실행 — **실 findings 는 클라우드(EC2+IAM)에서만**, 로컬은 자격증명 부재로 비거나 오류 |
| B4 | Slack 제안 알림 | `app.main` 로컬 실행(실 Slack 토큰 + `SLACK_NOTIFY_CHANNEL`) → 새 제안 시 채널 ping |
| B5 | 상주 모니터 dedupe | `python -m app.agent_monitor --loop 5` → 1건 제안 후 반복은 dedupe(스팸 없음) |
| B6 | (클라우드) write-denied | EC2 1회 → 쓰기 op 시도 → "denied by security policy" |

---

## 주의 / 메모
- **콘솔 에러 1건 = `favicon.ico` 404** — 기능 무관(무해).
- **낙관적 락 거부**(재승인 "이미 처리됨")는 이번 단일 세션 UI 로는 재현 안 함(승인 후 버튼 사라짐). 서버 `ConditionExpression`(status=awaiting_approval) 으로 강제 + 단위테스트·이전 QA(2탭 레이스)로 검증됨.
- 벨은 **agent 제안만** 표시(B6에서 넣은 `detect`/web 작업은 벨에 안 뜸 — 의도된 동작).
- 이 web-only 스택은 8930 점유 → `make demo` 전에 `cd web && docker compose down` 권장(make demo 가 자체 스택 기동).
