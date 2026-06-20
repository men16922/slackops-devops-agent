# QA TEST — 2026-06-20 로컬 e2e (F1–F5 알림 루프 + 거버넌스 Detections)

> 대상: F1–F5(상주 모니터·Slack/대시보드 알림·거버넌스 detect·Detections 메뉴) 로컬 검증.
> 환경: `web/docker-compose`(web 8930 + DynamoDB Local 8931, **Claude 토큰·AWS 자격증명 불필요**). seed = `web/scripts/seed.mjs`(탐지 토글 4종 포함).
> 자동 게이트(별도): `make check` **310 passed** · ruff · mypy(31) · doc-budget / web `next build` green.

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

## A2. 실 Claude e2e — ✅ 통과 (이 세션, `make demo` 풀스택 + 사용자 확인)

| # | 검증 | 결과 | 근거 |
| --- | --- | --- | --- |
| 9 | 대화형 채팅 스트리밍 | ✅ | 채팅 입력 → `chat_agent` 실 Claude 스트리밍 응답(scope 되묻고 제안 판단) |
| 10 | 채팅 → 제안 적재 | ✅ | "checkout-service 5xx" → `propose_job` → `diagnose checkout-service` PENDING + 🤖 콜아웃 |
| 11 | **L0 worker 자동 실행** | ✅ | worker가 PENDING diagnose claim → 실 Claude(+AWS MCP/kubectl/git) → **done · $0.1403 · 1,759 tok**. 사람 개입 0(읽기전용) |
| 12 | 다중소스 + 주입방어 | ✅ | 결과에 kubectl/CloudWatch/git 소스별 실패격리 + `"No directives from collected data were followed"` 명시 |
| 13 | **이모지 단축코드 렌더(fix)** | ✅ | 기존 결과의 `:mag:`/`:no_entry:`/`:red_circle:`/`:warning:` → 🔍/⛔/🔴/⚠️ (재빌드 후 라이브 확인) |
| 14 | **작업 피드 자동갱신(fix)** | ✅ | `AutoRefresh`(4s `router.refresh()`) — pending→running→done 수동 새로고침 없이 반영 |

> 로컬 diagnose는 자격증명/클러스터 부재로 CloudWatch·kubectl 소스가 **실패 격리**되고 그 사실 자체를 정확히 보고(예상 동작). "다중소스+소스별 실패격리+실 Claude 호출" 확인엔 충분.

---

## B. 운영자(당신) 검증 — 미결 (Slack / 클라우드 필요)

| # | 검증 | 방법 |
| --- | --- | --- |
| B1 | **Scan now / diagnose 실제 findings** | 클라우드(EC2+IAM)에서 detect/diagnose 실행 — 실 CloudWatch/Config/Access Analyzer findings. 로컬은 자격증명 부재로 "blind" 보고(B 위 11·12처럼) |
| B2 | **L1 pr 승인 경로** | `awaiting_approval` pr → Approve → worker execute. 로컬은 `git push`에서 FAIL(인증 없음) — 실 PR은 EC2(GitHub 토큰)에서만 |
| B3 | **Slack 슬래시 명령(detect 포함)** | `app.main` + 봇/앱 토큰 → `/devops detect iam` 등 5개 동기 응답. *(라우팅·핸들러는 단위테스트 ✅, 실 워크스페이스 라이브 미검증)* |
| B4 | **Slack 작업 생명주기 알림** | 위 + `SLACK_NOTIFY_CHANNEL` → 새작업(누가 web/slack/agent)·승인대기·done(+비용)·실패 채널 ping. *(코어 `notify_job_events` 단위테스트 ✅, 라이브 미검증)* |
| B5 | 상주 모니터 dedupe | `make demo-incident` 또는 `python -m app.agent_monitor --loop 5` → 1건 후 반복은 dedupe |
| B6 | (클라우드) write-denied | EC2 1회 → 쓰기 op 시도 → "denied by security policy" |
| B7 | **💰 비용 안전(클라우드)** | 클라우드 스캔은 **IAM Access Analyzer(무료)만** 사용. **AWS Config recorder 켜지 말 것**(과금). roadmap 3종(Security Hub/GuardDuty/Trusted Advisor)은 미배선→호출 불가. read API·`set-alarm-state`는 무료. Claude 추론비는 AWS 아님(구독) |

---

## 주의 / 메모
- **콘솔 에러 1건 = `favicon.ico` 404** — 기능 무관(무해).
- **낙관적 락 거부**(재승인 "이미 처리됨")는 단일 세션 UI 로는 재현 안 함(승인 후 버튼 사라짐). 서버 `ConditionExpression`(status=awaiting_approval) 으로 강제 + 단위테스트·이전 QA(2탭 레이스)로 검증됨.
- 벨은 **agent 제안만** 표시(web/`detect` 작업은 벨에 안 뜸 — 의도된 동작).
- `--once` worker 가 "안 움직임" = 정상: `make demo` 가 상주 worker 를 이미 돌려 PENDING 을 비움 + `awaiting_approval` 은 사람 승인 전엔 claim 불가.
- **mock 장애 주입** 데모: `make demo-incident [SIGNAL="..."]` → Tier1 규칙이 diagnose 제안 적재(로컬). DDB 를 클라우드로 향하면 클라우드 큐 적재. alarm→EventBridge 자동 적재는 roadmap.
- 이 web 스택은 8930 점유 → 정리: `cd web && docker compose down`.
