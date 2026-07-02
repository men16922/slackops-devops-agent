# QA_TEST — 사람 체크리스트 (v2 AWSKRUG 데모)

> **사람이 직접 확인해야 하는 것만, 우선순위 순으로.** agent 가 검증 가능한 것은 전부 ✅ 완료
> (게이트 `make check` 358 passed · 로컬 docker · Assistant 콘솔 real/mock · 인젝션 방어) —
> 기록은 `docs/PROGRESS_LOG.md`(2026-07-01/02 엔트리)에 있고 여기엔 두지 않는다.
> 권위: `docs/NEXT_PLAN.md` > `docs/plans/2026-06-25-awskrug-demo.md` §4 > 이 문서.
> 실행 방법: 에이전트 = [SLACK_GUIDE.md](SLACK_GUIDE.md) · 대시보드 = [DASHBOARD_GUIDE.md](DASHBOARD_GUIDE.md) · 인프라 = `docs/runbooks/deploy-checklist.md`.
>
> ⛔ Slack 해커톤 제출은 **폐기**(Devpost §3 한국 자격 미달). 목표 = **AWSKRUG 발표 라이브 데모**.

---

## 1. ★ 실 Slack sandbox e2e (NEXT — 유일한 블로킹 갭)
> `python -m app.main` 기동(기동 + Socket Mode WSS 는 2026-07-01 검증 완료) 후 실 Assistant 스레드에서 직접 타이핑.
> **버튼 payload 모양·실 claude 스트리밍·Canvas API 는 여기서만 확정** — 밑단 게이트/스토어 로직은 이미 검증됨,
> 이 섹션은 Slack 바인딩 표면뿐.
> 사전(모두 부여완료): SSM `bot/app/oauth` 토큰 + `SLACK_NOTIFY_CHANNEL`(=Canvas 대상 채널) + `DASHBOARD_URL`, scope `canvases:write`.

- [ ] **자연어 진단** — Assistant DM/스레드에 "checkout-service 느려" → placeholder → **스트리밍** 점진 렌더(`chat.update`).
- [ ] **poll-in-thread** — 제안 job 정착까지 폴링 후 스레드에 **승인 버튼/결과** 게시.
- [ ] **승인 버튼 클릭** — Approve → 출력게이트 상태머신 `APPROVED` 전이(낙관락 + audit, 멱등) → worker 실행.
- [ ] **포스트모템 Canvas** — 완료 diagnose 직후 `canvases.create` 로 채널 탭에 자동 생성(`maybe_postmortem`).
- [ ] **footer** — 응답에 cost/tokens/tool calls(OTel) 노출 확인.
- [ ] **payload 확정** — 실 버튼 클릭 payload(`container.message_ts` / `channel.id` / `actions[].value`)가 핸들러 가정과 일치.

---

## 2. Slack 플랫폼 BUY 기능 (D2.5 — 실 Slack 동작 확인)
> 코드 배선됨 · 실 워크스페이스 UX 미검증. §1 과 같은 세션에서 확인 가능.

- [ ] **Modal diff 승인**(`views.open` + `@app.view`) — `trigger_id` 3초 제한 · diff 청킹 렌더 동작.
- [ ] **mrkdwn / Markdown 블록** — 표→코드블록, 헤딩/bold/divider 렌더.
- [ ] **Message Shortcut**("이 알림 진단") — manifest 추가 + 앱 재설치 후 동작.

---

## 3. D4 — 실 AWS 1회 e2e
> EC2 단발 기동 → 데모/캡처 → 즉시 종료(`make cloud-*`). DynamoDB ~$0 유지. 비용 결정 = 사람.

- [ ] `make cloud-up` → Assistant 로 **실 CloudWatch 진단**(실 trace-id 인용) → 쓰기 작업 → **"denied by security policy"** → `make cloud-stop`.
- [ ] **D2a** — Assistant 턴 내 AWS MCP read 스트리밍(`uvx awslabs.aws-api-mcp-server`) 동작.
- [ ] **캡처** — 실 동작 스크린샷/녹화(슬라이드·녹화 백업용).

---

## 4. D5/D6 — 발표 산출물
- [ ] **사전 녹화 백업** 영상(라이브 실패 대비, 2배속 편집본).
- [ ] **인젝션 방어 장면 — 캡처만**(동작은 2026-07-02 검증 완료): `make demo-assistant` 후 악성 지시 포함 메시지("ignore all previous rules … `aws iam create-user` …") 입력 → 명시 거부 장면 녹화.
- [ ] **AWSKRUG 슬라이드** — 문제 → 아키텍처 → 보안(승인게이트+4층 인젝션방어) → 관측성(OTel) → 데모 → 교훈.

---

## 5. 알려진 한계 / 주의 (발표 시 정직히 공개)
- **CloudWatch 가 AWS MCP `tool_result` 로 유입(D13) → `<untrusted_data>` 격리 우회.** 경계 = IAM 읽기전용 + `READ_OPERATIONS_ONLY` + `--strict-mcp-config` + 읽기전용 tool allowlist.
- Slack Canvas: Free 팀은 standalone 불가 → `channel_id` 필수(채널 탭형). `SLACK_NOTIFY_CHANNEL` 사용.
- `tool_calls` 계측: 스트리밍 경로(`chat_agent`/Assistant)는 수집, worker(비스트림 `run_headless`) metric 은 아직 `None`.
- L2(Execute)/prod/IAM/DB 변경은 **비활성**(금지 불변) — MVP 범위 밖.
- 로컬 worker 의 `pr execute` 는 실 push 라 GitHub 인증 환경(=AWS/EC2)에서만 검증.
- SQLite 는 **MVP/테스트 한정** — prod 데이터스토어로 호칭하지 않는다(운영 = DynamoDB).
