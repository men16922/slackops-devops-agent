# PLAN — 안전 자율 루프 닫기 (monitor 상주 + Slack/대시보드 알림) + H0 산출물

작성: 2026-06-20 · 대상 마감: 2026-06-29 · 권위: NEXT_PLAN > 이 문서

> **결정(사용자 확정):** ① 순서 = **기능 먼저 → Vercel 배포**. ② 산출물 = 코드 + **DevPost 설명 초안 + 3분 데모 스크립트 문서까지** 작성.

---

## 0. 왜 (Context)

지금 에이전트는 *신호 감지 → 작업 제안*(agent_monitor Tier1/Tier2 + chat_agent 대화형 제안)까지 되지만:
- monitor 가 **상주하지 않음** — 사람이 `make agent-monitor` 칠 때만 실행(EC2 systemd 3개: slack/worker/chat-agent 뿐).
- 제안이 큐에 **조용히** 쌓일 뿐 Slack·대시보드 **알림 없음** → 사람이 직접 보러 가야 함.

세 기능을 합치면 루프가 **눈에 보이게 닫힌다**: *에이전트 감지 → Slack ping + 대시보드 벨 → 사람이 rationale 확인 → 승인 게이트 → worker 실행*. 이 연속 흐름이 H0 데모의 가장 강한 서사이고, 모든 조각이 **단일 DynamoDB 큐**를 읽어 DB 중심 스토리를 강화한다.

---

## 1. 기능 1 — agent_monitor EC2 상주 (+ 중복 제안 가드)

`--loop N` 상주 모드는 이미 있음 → systemd 유닛 + **dedupe 가드**만 추가(정적 `_DEMO_SIGNALS` 상주 시 같은 작업 무한 재제안 방지).

- **dedupe 가드 = `src/app/mcp_server.py` `propose_job_impl`** (단일 chokepoint — monitor Tier1·Tier2·chat_agent 제안 전부 커버).
  `_has_open_agent_duplicate(store, command, args)`: `list_recent(50)` 스캔 → 동일 `source=AGENT` 작업이 `pending`/`awaiting_approval` 면 True. 중복이면 `{"ok": True, "deduped": True, "job_id": None, "status": "skipped"}` 반환(무해 no-op; `simulate_detection` 기존 `isinstance(job_id, str)` 가 None 처리 → monitor 수정 불필요). `source=AGENT` 로 한정. `args.strip()` 정규화 불변 주석.
- **4번째 systemd 유닛** (`deploy/ec2/user-data.sh`): `slackops-devops-agent-monitor.service`, `ExecStart=… -m app.agent_monitor --loop 300`, `Restart=always`, 동일 `EnvironmentFile`. `systemctl enable --now` 목록에 추가. 기본 **Tier1**(`--real` 없음 → 토큰 0). Tier2 는 on-demand.
- **정직한 한계(유닛 주석 + features 문서):** `--signals-file` 없이 상주 시 같은 데모 신호만 관찰 = "에이전트 heartbeat"(라이브 관찰 아님). dedupe 가드가 비-spam 의 핵심. 실관찰은 `--signals-file`(CloudWatch 덤프) 또는 `--real`.
- **테스트**(`tests/test_mcp_propose.py`, `test_agent_monitor.py`): 동일 open agent 중복; args 다르면 비중복; terminal 후 비중복; AGENT 한정(web job 무시); `simulate_detection` 2회 → 2번째 None, 1건 저장.

## 2. 기능 2 — Slack 알림 (새 제안 시)

producer-무관: **큐**를 감시(monitor + chat_agent 모두 캐치). 코어는 순수/테스트 가능, **slack 앱 프로세스의 daemon thread** 로 호스팅(5번째 유닛 불필요, Bolt 앱의 인증된 client 재사용).

- **신규 `src/app/proposal_notifier.py`** (순수 `app.store.base` 만 import → import-safe, 모듈 top 에 Slack dep 없음):
  - `notify_new_proposals(store, post_fn, seen: set[str]) -> list[str]` — `reversed(list_recent(50))`(시간순), open `source=AGENT` & not in `seen` 마다 `post_fn(format_proposal(job))` 후 `seen.add`; 작업별 try/except.
  - `format_proposal(job)` — `🤖 New agent proposal — \`command\` \`args\`` + rationale 인용 + `Approve/reject: <DASHBOARD_URL>/jobs/<id>`(미설정 시 `(job <id>)`).
  - `run_forever(store, post_fn, *, poll_interval_s=5.0, max_iterations, sleep)` — worker/chat_agent 패턴. `make_post_fn(client, channel)` closure.
- **`src/app/main.py`**: `_serve_proposal_notifier(handler)` daemon thread 를 blocking `handler.start()` 전에 기동. `SLACK_NOTIFY_CHANNEL` 미설정 시 no-op. `handler.app.client.chat_postMessage` + `store_from_env()`. top-level try/except(죽어도 slack 앱 안 죽음 — health thread 선례).
- **env**(user-data 추가): `SLACK_NOTIFY_CHANNEL`(미설정→비활성), `DASHBOARD_URL`.
- **재시작 dedupe:** in-memory `seen` 셋(해커톤 선택 — 재시작 시 open 제안 1회 재게시, 허용 범위). 영속 `notified_at` 플래그(스키마 손댐)는 "production 업그레이드"로 보류.
- **테스트**(`tests/test_proposal_notifier.py`): open agent 만 게시(web/terminal 제외); seen-셋 dedupe; 메시지 포맷(deep-link + fallback); 비어있을 때 sleep; post 실패 시 id unseen 유지.

## 3. 기능 3 — 대시보드 알림 벨

순수 프론트, 기존 `Chat.tsx` 폴링 + localStorage 패턴 미러. 같은 큐를 읽음.

- **`web/lib/ddb.ts`**: `listPendingAgentJobs(limit=50)` = `listRecentJobs` 를 `source==="agent"` & `pending`/`awaiting_approval` 필터(새 GSI 불필요).
- **`web/app/api/jobs/agent-pending/route.ts`**(`app/api/chat/[conv]/route.ts` 미러, `export const dynamic="force-dynamic"`): GET → `{ jobs }`.
- **`web/app/NotificationBell.tsx`**(`"use client"`): `/api/jobs/agent-pending` ~4s 폴링(`setInterval`, `cache:"no-store"`, cleanup). 워터마크 `lastSeen` = localStorage(ISO `created_at`). unread = `created_at > lastSeen`. 벨 🔔 + unread 카운트 뱃지(`--red`); 드롭다운(command + rationale, `<Link href="/jobs/{id}">`, `.src-agent`/`--green` 재사용); "Mark all seen" → 워터마크를 최대 visible `created_at` 로.
- **`web/app/layout.tsx`**: `.topbar-right` 래퍼에 `<NotificationBell/>` + `.src` 배치. `globals.css` 최소 추가(기존 토큰 재사용, 새 색 없음).
- **검증**: `next build`(route/component/`Job` 타입 체크; `Job` 타입 필드 이미 충분).

## 4. 기능 4 — 문서/산출물 (사용자 확정: 초안까지)

- **`docs/guide/kr/features.md`(+ en)**: monitor 상주 + Slack/대시보드 알림 행 추가.
- **신규 `docs/guide/kr/DEVPOST.md`(+ en)**: DevPost 제출 설명 초안 — 무엇/누구/왜 + "AWS Database used: **DynamoDB**" + DB 정당화 한 문장 + 보안(L0/1·주입방어 4계층)·관측(OTel) 차별화 + 정직한 한계(QA_TEST §3). AI 초안 → 본인 목소리 편집 필요 명시.
- **신규 `docs/guide/kr/DEMO_SCRIPT.md`(+ en)**: 3분 데모 스크립트(샷 리스트).
  - 스파인(연속 take): 문제/대상(온콜 토일 ~20s) → agent_monitor 감지 → **Slack ping + 대시보드 벨 점등**(wow) → 제안 열어 rationale → **diff 승인 게이트** → worker 실행 → telemetry(비용/토큰). 보안(Socket Mode 인바운드 0·IAM Instance Profile·주입 격리·L0/1)을 화면에 녹임. DB 정당화 문장으로 마무리.

---

## 5. 실행 순서 (기능 먼저 → 배포)

1. **기능 1·2 (Python)** — dedupe 가드 + proposal_notifier + main.py thread + systemd 유닛 + 테스트 → `make check`(목표 유지: pytest 전부 green + ruff + mypy strict + doc-budget).
2. **기능 3 (web)** — ddb/route/NotificationBell/layout/css → `web` 에서 `next build` green.
3. **로컬 e2e** — `make demo` 로 감지→Slack(옵션)→벨→승인→실행 풀 루프 1회 육안 확인.
4. **기능 4 문서** — features 갱신 + DEVPOST/DEMO_SCRIPT 초안.
5. **/checkpoint** — STATUS/NEXT_PLAN/PROGRESS_LOG 반영, 커밋.
6. **그 다음 Vercel 배포** — `DASHBOARD_GUIDE §7`(읽기전용 IAM 키, Root=`web`, `DDB_ENDPOINT` 미설정) → Team ID/링크. 알림 벨 포함된 빌드가 배포됨.

## 6. 리스크
1. dedupe 50-item 윈도 — 50개 밑에 묻힌 open 중복은 통과(허용·문서화).
2. notifier in-memory seen — 재시작 시 open 제안 1회 재게시(허용; 영속 플래그=업그레이드).
3. notifier-slack 프로세스 결합 — thread top-level try/except 로 완화.
4. `args` 정규화 drift(가드↔enqueue) — 불변 주석.
5. topbar `.src` `margin-left:auto` — `.topbar-right` 래퍼로 처리.

## 7. 검증
- Python: `make check` + import-safety(`python -c "import app.proposal_notifier, app.mcp_server, app.agent_monitor"` — slack/boto3 미설치에서도 성공).
- Web: `web` 에서 `next build`.
- 수동(선택): `python -m app.agent_monitor --loop 5` → 1건 제안 후 dedupe; 벨 증가 후 "mark all seen" 으로 클리어; `SLACK_NOTIFY_CHANNEL` 설정 시 채널 1회 게시.

## 8. 핵심 파일
- `src/app/mcp_server.py`(dedupe), `src/app/main.py`(notifier thread), **신규** `src/app/proposal_notifier.py`
- `deploy/ec2/user-data.sh`(4번째 유닛 + env)
- **신규** `web/app/NotificationBell.tsx`, **신규** `web/app/api/jobs/agent-pending/route.ts`, `web/lib/ddb.ts`, `web/app/layout.tsx`, `web/app/globals.css`
- 테스트: **신규** `tests/test_proposal_notifier.py`, `tests/test_mcp_propose.py`, `tests/test_agent_monitor.py`
- 문서: `docs/guide/{kr,en}/features.md`, **신규** `docs/guide/{kr,en}/DEVPOST.md`·`DEMO_SCRIPT.md`
