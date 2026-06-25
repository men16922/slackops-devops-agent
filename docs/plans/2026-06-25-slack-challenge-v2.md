# Plan — Slack Agent Builder Challenge v2 (2026-06-25)

> 전략 + 설계 문서. 권위는 docs/NEXT_PLAN.md(작업 목록) > 이 문서(전략 근거).
> 베이스 브랜치: `v2` (from `origin/main` @ 37ff697). 직전 제출(H0 해커톤)과의 차이를 명시.
> ⚠️ 일정/자격 조항은 사용자 제공 정보 기반 — **제출 전 Devpost 공식 규정 원문 재확인 필수**(아래 §1 체크박스).

---

## 1. 대회 개요 (Slack Agent Builder Challenge)

| 항목 | 내용 |
|---|---|
| 주최 / 주관 | Salesforce(Slack) / Devpost |
| 목표 | Slack AI · MCP 서버 연동 · 실시간 검색 API **중 ≥1개**를 활용한 AI 에이전트 앱 |
| 제출 마감 | **2026-06-29(월) 17:00 PT = 06-30(화) 09:00 KST** (원 7/13 → 4일 앞당겨짐) |
| 심사 | 7/14 ~ 8/6 (AI 분석 + 전문가 패널) |
| 발표 | 8/11 전후, 총 9개 팀 |
| 총상금 | $74,400 |
| **중복 제출 제한** | 타 대회 제출작 **그대로 복사 불가**. **신규 개발 or 대대적 업데이트** 작품만 인정 |

- [ ] **(제출 전)** Devpost 공식 페이지에서 마감 시각·자격 기술 목록·중복 제출 조항 원문 재확인
- [ ] **(제출 전)** "Slack AI"의 정확한 정의 확인 (Slack 유료 AI / Agentforce / Assistant API 중 무엇이 인정되는지)

---

## 2. 핵심 판정: **조건부 가능 — "리스킨"이 아닌 "Slack-네이티브 v2"**

직전 제출(H0: "Hack the Zero Stack with Vercel v0 + AWS Databases", 마감 6/30)과 **동일 코드베이스**.
그대로 내면 탈락 리스크. 그러나 적합성은 오히려 H0보다 이 대회에 더 높음 → **재포지셔닝하면 경쟁력 있음**.

### 자격(중복 제출) 판정
- 규칙은 "**대대적 업데이트면 인정**"을 명시 → **합법. 단 입증 책임은 우리에게.**
- 입증 수단 = **git 히스토리**(대회 기간 내 신규 커밋) + **신규 기능** + **Slack 중심 신규 서사/데모**.
- 위험: 코스메틱 변경만이면 "AWS 프로젝트 재활용"으로 평가절하 → §4 P0 작업으로 차단.

---

## 3. 자산 인벤토리 (재사용 가능 — 4일 내 현실성의 근거)

| 영역 | 자산 | v2 처리 |
|---|---|---|
| Slack | Bolt Socket Mode + `/devops` 라우팅 (`slack_handler.py`) | **재플랫폼** (slash → Assistant) |
| 추론 | Claude Code Headless subprocess + **stream-json** (`claude_runner.run_headless_stream`) | **그대로 재사용** (스트리밍 응답의 토대) |
| 대화 | `chat_agent.py` 폴링 컨슈머 + 대화 버스(`chat_store.py`) | Assistant 스레드로 흡수/이식 |
| 보안 | 권한 L0/L1 + 4층 인젝션 방어(sanitizer/allowlist/output gate/template) | **그대로 — 핵심 차별점** |
| MCP | `aws-api-mcp-server` 연동 + 자체 FastMCP(`mcp_server.py`) | **요구사항 충족 증거** (그대로) |
| 관측성 | OTel span + cost/token 계측(`telemetry.py`) | 그대로 — 차별점 |
| 큐/스토어 | 단일테이블 Job/Audit/Telemetry (sqlite+dynamodb) + worker 출력게이트 | 그대로 (구현 디테일로 강등) |
| 검증 | pytest 310 passed / ruff / mypy strict | 회귀 가드 |

**결론:** 백엔드·보안·관측성은 완성. **부족한 건 "Slack 에이전트다움"(UX 패러다임)과 서사 방향**뿐.

---

## 4. Gap 분석 & v2 전략

### Gap A — 서사가 AWS용
- 직전 `DEVPOST.md`의 핵심은 "**Why DynamoDB**" / "Vercel 듀얼 컨트롤플레인". Slack 심사에선 **주제 이탈**.
- **전략:** DynamoDB/Vercel을 "구현 디테일"로 강등. 전면에 **"Slack 안에서 안전하게 일하는 AI DevOps 동료"**.
  - 살아남는 차별점(플랫폼 무관): **승인 게이트 + 4층 인젝션 방어 + 풀 OTel**.

### Gap B — UX가 구식 봇 (slash command)
- 현 진입점 = `/devops <subcmd>` 단일 슬래시 커맨드(`slack_handler.py:113`). "봇"이지 "에이전트" 아님.
- **전략:** **Slack Assistant API**로 재플랫폼 — 에이전트 스레드 + 스트리밍 응답 + suggested prompts.
  - `run_headless_stream` + `chat_agent` 로직 대거 재사용 → 신규 구현 부담 최소.

### Gap C — 요구사항 2번째 축(차별화)
- MCP는 이미 충족. 가점을 위해 **실시간 검색 API**로 "research/triage" 능력 추가 고려(P1).

---

## 5. 설계 — Slack Assistant 재플랫폼

### 목표 UX
```
사용자가 Slack에서 봇 DM/Assistant 패널 오픈
  → "checkout-service가 느려" (자연어, 슬래시 없음)
  → 에이전트가 스레드에서 **스트리밍**으로 사고/진단 표시 (suggested prompts 제공)
  → 위험 작업(PR 등)은 diff를 스레드에 먼저 게시 → 사람 승인 버튼 → worker 실행
  → 비용/토큰/소요시간(OTel) 요약 footer
```

### 아키텍처(변경분만)
```
Slack Assistant(threads + streaming) ──┐
                                       ├─→ 기존 라우팅/권한/sanitizer/allowlist (그대로)
(폐기 아님) /devops slash = 호환 유지 ──┘        ↓
                                       Claude Code Headless (run_headless_stream)
                                       ↓ 위험 작업 → 출력게이트(diff→승인) → worker
                                       단일테이블 큐 + OTel (그대로)
```

### 구현 포인트
- `slack_handler.py`에 **Assistant 핸들러 추가**(`app.assistant` / `assistant_thread_started` · `user_message` 이벤트).
  슬래시 커맨드는 **유지**(호환 + 데모 폴백).
- 자연어 입력 → 기존 `route()`/커맨드 매핑으로 의도 분류(또는 Claude가 직접 도구 선택). **sanitizer/allowlist 경유 불변**.
- 스트리밍 = `run_headless_stream`(stream-json) → Slack `chat.update`로 점진 렌더(`chat_agent`의 폴링 렌더 로직 이식).
- 승인 게이트 = 스레드 내 Block Kit 버튼(Approve/Reject) → 기존 worker 출력게이트 상태머신 재사용.

---

## 6. 4일 실행 계획 (6/25–6/29)

> 규칙: 한 번에 하나, 변경마다 `pytest` 풀런 + 커밋(신규 git 히스토리 = 자격 입증).

| Day | 우선 | 작업 | Done 기준 |
|---|---|---|---|
| **D1 (6/25)** | P0 | Assistant 핸들러 스캐폴드 + 자연어→의도 라우팅(로컬 단위테스트) | 새 테스트 green, gate 유지 |
| **D2 (6/26)** | P0 | 스트리밍 응답(스레드 점진 렌더) + 승인 버튼 게이트 이식 | 로컬 e2e: 진단→diff→승인 |
| **D2–3** | P1 | (선택) 실시간 검색 API or 추가 MCP로 research 능력 | 데모 가능한 신규 기능 1개 |
| **D3 (6/27)** | P0 | 서사 재작성: `docs/submission/` v2 DEVPOST/데모 스크립트(Slack 중심) | 초안 완성 |
| **D3–4** | P0 | 클라우드 캡처(EC2 재기동) — Assistant UX 실 Slack e2e | 영상용 캡처 확보 |
| **D4 (6/28)** | P0 | 3분 데모 영상 + 아키텍처 다이어그램(Slack 강조) + 제출 폼 | 제출 직전 상태 |
| **D4–5 (6/29)** | P0 | 최종 점검 + **공식 규정 재확인** + 제출 | 제출 완료 |

---

## 7. 제출물 체크리스트
- [ ] 텍스트 설명 — Slack 에이전트 중심(보안+승인게이트+OTel 차별점), DynamoDB/Vercel은 디테일
- [ ] 3분 데모 영상 — Assistant 스레드 자연어 → 스트리밍 진단 → 승인 게이트
- [ ] 아키텍처 다이어그램 — Slack Assistant 전면
- [ ] 공개 리포 링크 + **대회 기간 git 히스토리**(신규 개발 입증)
- [ ] 요구사항 충족 명시 — **MCP 서버 연동**(+ 가능 시 실시간 검색 API)
- [ ] (있다면) Slack workspace 설치/테스트 안내

---

## 8. 리스크 & 완화
| 리스크 | 완화 |
|---|---|
| 중복 제출로 평가절하 | P0 재플랫폼(실질 신규) + 대회 기간 커밋 + Slack 신규 서사/데모. "선행 오픈소스를 본 챌린지용으로 대대적 확장" 정직 표기 |
| Assistant API 미경험 → 4일 초과 | slash 커맨드 폴백 유지(최악의 경우 기존 UX로 제출 가능). 백엔드는 무변경 |
| "Slack AI" 자격 기준 오해 | §1 체크박스로 제출 전 공식 확인. MCP 충족분이 안전망 |
| 클라우드 캡처 비용/시간 | EC2 단발 기동→캡처→종료 (기존 `make cloud-*` 라이프사이클) |

---

## 9. 의사결정 필요(사용자)
1. **재플랫폼 범위**: full Assistant API 재플랫폼(권장) vs slash 유지+스트리밍만 보강(보수적).
2. **P1 신규 기능**: 실시간 검색 API 추가 여부(가점 vs 4일 압박).
3. **제출 전 공식 규정 검증**: 내가 Devpost 페이지 fetch해 §1 체크박스 채울지.
