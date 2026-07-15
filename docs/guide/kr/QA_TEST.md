# QA_TEST — 사람 체크리스트 (v2 AWSKRUG 데모)

> **사람이 직접 확인해야 하는 것만, 우선순위 순으로.** agent 가 검증 가능한 것은 전부 ✅ 완료
> (게이트 `make check` 358 passed · 로컬 docker · Assistant 콘솔 real/mock · 인젝션 방어) —
> 기록은 `docs/PROGRESS_LOG.md`(2026-07-01/02 엔트리)에 있고 여기엔 두지 않는다.
> **Part A (LOCAL)** 는 이 Mac 에서 전부 수행 — `make demo-all` + 실 Slack 워크스페이스 연결, EC2 불필요, ~$1.
> **Part B (REAL AWS)** 는 유료 EC2 1회 — Part A 통과 후 수행.
> 권위: `docs/NEXT_PLAN.md` > `docs/plans/2026-06-25-awskrug-demo.md` §4 > 이 문서.
> 실행 방법: 에이전트 = [SLACK_GUIDE.md](SLACK_GUIDE.md) · 대시보드 = [DASHBOARD_GUIDE.md](DASHBOARD_GUIDE.md) · 인프라 = `docs/runbooks/deploy-checklist.md`.
>
> ⛔ Slack 해커톤 제출은 **폐기**(Devpost §3 한국 자격 미달). 목표 = **AWSKRUG 발표 라이브 데모**.

---

# Part A — LOCAL (이 Mac · EC2 불필요)
> 준비 1회: `make demo-all`(web 8930 + DynamoDB Local + chat_agent + worker + Slack 앱 Socket Mode).
> 기동 + WSS 는 2026-07-01 검증 완료. 실 Slack 워크스페이스 네트워크 연결은 필요하지만 AWS 인프라는 0.
> 사전(모두 부여완료): `.env`/SSM `bot/app/oauth` 토큰 + `SLACK_NOTIFY_CHANNEL`(=Canvas 대상 채널) + `DASHBOARD_URL`, scope `canvases:write`.

## A1. ★ 실 Slack sandbox e2e — ✅ 전부 통과 2026-07-02 (일반 DM 폴백 경로)
> 앱 DM 에서 라이브 검증(`register_dm_messages` — ✨ 어시스턴트 패널은 유료 표면이라 DM 폴백으로 커버).
> 증빙은 PROGRESS_LOG 2026-07-02.

- [x] **자연어 진단** — "checkout-service is slow" → 스트리밍 렌더(`chat.update`, "(edited)") + 제안. 2026-07-02.
- [x] **poll-in-thread** — pr 제안 정착 → **diff 미리보기 + ✅/❌ 버튼** DM 게시. 2026-07-02.
- [x] **승인 버튼 클릭** — `awaiting_approval → approved`(낙관락) + 버튼 메시지 "approved by @…" 갱신. 로컬 execute 는 의도적 생략(실 push = D4/EC2). 2026-07-02.
- [x] **포스트모템 Canvas** — 완료 diagnose 가 채널 탭 Canvas 자동 생성("Postmortem — checkout-service" in #devops) + "Drafted…" 안내. 2026-07-02.
- [x] **footer** — `$0.3673 · 4933 tokens · 2 tool calls` 노출. 2026-07-02.
- [x] **payload 확정** — 실 클릭 payload 가 핸들러 가정과 일치: `actions[].value`=job id, `user.id`=U0BBX3U5Q2W, audit `approved · via slack`. 2026-07-02.

## A2. Slack 플랫폼 BUY 기능 (D2.5)
- [x] **mrkdwn / Markdown 블록** — A1 세션에서 헤딩/bold/불릿/인라인코드 렌더 확인. 2026-07-02.
- [x] **Modal diff 승인 / Message Shortcut 구현** — full-diff modal, malformed-state 거부, 승인자 allowlist,
  조건부 상태 전이, 원본 메시지 갱신, shortcut 추출을 로컬 테스트로 확인. 2026-07-15.
- [ ] **실 Slack 검증** — Slack App에 Message Shortcut callback ID `review_slackops_job`을 등록한 뒤 SlackOps 승인
  메시지에서 **Review diff**를 열어 승인/거부한다. 비허용 사용자는 modal을 열거나 상태를 바꾸지 못하고, 허용
  사용자의 결정은 원본 메시지와 감사 피드에 남아야 한다.

## A3. 발표 산출물 (D5/D6)
- [ ] **인젝션 방어 장면 — 라이브 시연으로 대체**(동작은 2026-07-02 검증 완료). 별도 캡처 불필요.
- ~~사전 녹화 백업~~ **폐기** — 라이브 시연 + 로컬 mock 폴백(`make demo-assistant-mock`)으로 대체.
- [ ] **AWSKRUG 슬라이드 디자인** — 문제 → 아키텍처 → 보안(승인게이트+4층 인젝션방어) → 관측성(OTel) → 데모 → 교훈.

---

# Part B — REAL AWS (EC2 1회 · Part A 이후)
> `make cloud-up` → 데모/캡처 → 즉시 종료(`make cloud-stop`/`cloud-down`). DynamoDB ~$0 유지.
> 비용 결정 = 사람. 데모 포인트가 **IAM Instance Profile(저장 키 0개)** 라 로컬 AWS 키로 대체하지 않는다.

- [x] `make cloud-up` → **실 CloudWatch 진단**(`handle_diagnose("checkout-service")` via AWS API MCP `call_aws` — 실 log-streams/events 조회, P1 진단 리포트 생성 ~90s) → 쓰기 작업(`delete_log_group`/`create_log_group`) → **"Execution of this operation is denied by security policy."** → `make cloud-stop`. 2026-07-06. EC2 `i-080db608831f628c5`, running ~15min, ~$0.01.
- [x] **D2a** — AWS MCP read 동작 확인: `mcp__awsapi__call_aws`가 `READ_OPERATIONS_ONLY=true` + Instance Profile(저장 키 0개)로 CloudWatch 읽기 성공, 변형 작업 즉시 거부. 2026-07-06.
- [ ] **캡처** — ~~실 동작 스크린샷/녹화(슬라이드·녹화 백업용)~~ **폐기**: 라이브 시연으로 대체(사전 녹화 안 함).

---

## 알려진 한계 / 주의 (발표 시 정직히 공개)
- **CloudWatch 가 AWS MCP `tool_result` 로 유입(D13) → `<untrusted_data>` 격리 우회.** 경계 = IAM 읽기전용 + `READ_OPERATIONS_ONLY` + `--strict-mcp-config` + 읽기전용 tool allowlist.
- Slack Canvas: Free 팀은 standalone 불가 → `channel_id` 필수(채널 탭형). `SLACK_NOTIFY_CHANNEL` 사용.
- **⏰ Canvas 생성이 현재 무료 트라이얼(7/19 종료)로 동작 중** (Slack 배너: "Creating canvases … is a paid feature"). **데모/캡처를 7/19 전에** 하거나 유료 워크스페이스 대비.
- `tool_calls` 계측: 스트리밍 경로(`chat_agent`/Assistant)는 수집, worker(비스트림 `run_headless`) metric 은 아직 `None`.
- L2(Execute)/prod/IAM/DB 변경은 **비활성**(금지 불변) — MVP 범위 밖.
- 로컬 worker 의 `pr execute` 는 실 push 라 GitHub 인증 환경(=AWS/EC2)에서만 검증.
- SQLite 는 **MVP/테스트 한정** — prod 데이터스토어로 호칭하지 않는다(운영 = DynamoDB).
