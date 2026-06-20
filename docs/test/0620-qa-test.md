# QA TEST — 2026-06-20 (F1–F5 알림 루프 + 거버넌스 Detections)

> 자동 게이트: `make check` **310 passed** · ruff · mypy(31) · doc-budget / web `next build` green.
> 로컬 환경: `make demo`(web 8930 + DynamoDB Local 8931 + worker/chat_agent). Slack까지: `make demo-all`(.env 토큰).

---

## ✅ 이미 검증됨 (이번 세션 — 재확인 불필요)
- **대시보드(Playwright 직접):** 렌더·nav · 🔔벨(unread/드롭다운/mark seen) · Detections 메뉴(시드 토글) · **Scan now→detect 작업 적재** · 출력게이트(diff) · **승인 전이**(approved+audit).
- **실 Claude L0 풀루프:** 채팅 스트리밍→제안→**worker 자동 실행 done $0.1403** · 다중소스+주입방어 보고.
- **수정분:** 이모지 단축코드 렌더(🔍/⛔/🔴/⚠️) · 작업 피드 자동갱신(`AutoRefresh`).
- **스케줄러/주입:** `make demo-incident` 라이브(diagnose 제안 + ON·scheduled iam 스캔 적재).
- 증빙: `.playwright-mcp/` 스냅샷.

---

## 🖥️ 로컬 체크리스트 (남은 것 — 토큰만 있으면 가능)

- [~] **Slack 슬래시 명령(5개)** — `/devops ping` ✅ 라이브 확인. logs/diagnose/detect/tf-review 미확인(같은 경로).
- [x] **Slack 작업 생명주기 알림** — ✅ **라이브 확인**(2026-06-20): `make demo-all` + `SLACK_NOTIFY_CHANNEL` →
      `🤖 Agent proposal — diagnose checkout-service` + `detect iam`(스케줄러) 채널 ping(rationale + deep-link).
      *(done/실패 이벤트 알림은 코어 단위테스트 ✅, 라이브 추가 확인 권장 — 작업 1건 done까지)*
- [ ] **상주 모니터 dedupe** — `make demo-incident` 2회 → 2번째는 dedupe(같은 제안 안 쌓임). *(단위테스트 ✅)*
- [ ] **L1 pr 승인 흐름** — `awaiting_approval` pr → 대시보드 Approve → worker가 approved claim → execute
      **시도**(로컬은 `git push`에서 FAIL=정상). 진짜 PR은 클라우드/`gh auth login` 환경.

> Slack 명령(logs/diagnose/detect/tf-review)은 **큐 안 거치고 즉시 실행→응답**. notifier만 큐를 읽어 채널 중계.

---

## ☁️ 클라우드 체크리스트 (EC2 + 실 AWS 필요 — 제출 캡처용)

- [ ] **실 CloudWatch diagnose** — `/devops diagnose <svc>` → Instance Profile로 실 로그/트레이스 진단.
- [ ] **실 거버넌스 스캔 findings** — Detections Scan now / `/devops detect iam` → **실 IAM Access Analyzer findings**.
- [ ] **write-denied** — 쓰기 op 시도 → `"denied by security policy"`(read-only 경계 증명). ★ 제출 강추 컷.
- [ ] **실 DynamoDB 데이터 + 콘솔 스크린샷** — Job/Audit/Metric 실 항목.
- [ ] *(선택)* **alarm 트리거** — `aws cloudwatch set-alarm-state … ALARM` → 신호 주입 흐름(EventBridge 자동 적재는 roadmap).
- [ ] **💰 비용 안전** — 클라우드 스캔은 **IAM Access Analyzer(무료)만**. **AWS Config recorder 켜지 말 것**(과금).
      roadmap 3종(Security Hub/GuardDuty/Trusted Advisor)은 미배선→호출 불가. read API·`set-alarm-state`는 무료. Claude 추론비는 AWS 아님(구독).

---

## 주의 / 메모
- **`.env` 자동 로드**: `make demo`/`demo-all`/`slack` 가 `.env`(gitignored, 로컬 전용) source → 토큰 수동 export 불필요. EC2는 영향 없음(SSM→env 파일).
- **pr GitHub 인증**: push/PR은 표준 git/gh CLI(`gh auth login`) — `.env`의 `GITHUB_APP_*`는 **미배선 placeholder**(채울 필요 없음).
- **낙관적 락 거부**(재승인 "이미 처리됨")는 단일 세션 UI론 재현 안 함 — 서버 `ConditionExpression` + 단위테스트/이전 QA(2탭 레이스)로 검증됨.
- 벨은 **agent 제안만** 표시(web/`detect` 작업은 벨에 안 뜸 — 의도).
- `--once` worker가 "안 움직임"=정상: `make demo`가 상주 worker로 PENDING을 비움 + `awaiting_approval`은 승인 전 claim 불가.
- 정리: `cd web && docker compose down` (또는 `make demo`/`demo-all` Ctrl-C).
