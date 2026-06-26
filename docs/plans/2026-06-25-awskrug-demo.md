# Plan — Slack-native v2 → **AWSKRUG 발표용 데모** (2026-06-25, 피벗 2026-06-26)

> 전략 + 설계 문서. 권위는 docs/NEXT_PLAN.md(작업 목록) > 이 문서(전략 근거).
> 베이스 브랜치: `v2` (from `origin/main` @ 37ff697).
>
> ## ⛔ 피벗 (2026-06-26): Slack 해커톤 제출 → 폐기, 목표를 AWSKRUG 발표로 전환
> Devpost 공식 Rules(`slackhack.devpost.com/rules`) §3 Eligibility 확인 결과 **한국 거주자는 참가 자격 없음**
> (Eligibility Area 16개국에 일본 포함, **South Korea 미포함**; "VOID OUTSIDE OF THE ELIGIBILITY AREA").
> → **해커톤 제출 작업(Devpost 폼/sandbox URL/제출영상/심사용 서사/Real-Time Search 3-of-3 요건) 전부 폐기.**
> → 새 목표 = **AWSKRUG(한국 AWS 사용자 모임) 발표에서 임팩트를 주는 라이브 데모**. 대폭 축소.
> (해커톤 규정 원문은 git 히스토리/§부록 참고 — 아래 본문은 새 목표 기준으로 재작성.)

---

## 1. 새 목표 — AWSKRUG 발표 임팩트

**한 문장:** "Slack에서 **한국어 자연어**로 말하면, AI DevOps 에이전트가 **실제 AWS를 안전하게 진단**하고,
위험한 작업은 **사람 승인 게이트**를 거쳐 실행한다 — 비용/토큰까지 투명하게."

청중 = AWS 실무자(SRE/DevOps/플랫폼). 임팩트 포인트 3개:
1. **Agentic + MCP** — Slack Assistant 스레드 자연어 → AWS API MCP(`aws-api-mcp-server`)로 실 CloudWatch 진단.
2. **안전성** — 승인 게이트(diff 먼저 게시 → 사람 승인) + **4층 프롬프트 인젝션 방어** (실무자가 가장 공감하는 차별점).
3. **관측성** — 매 응답 footer에 cost/tokens/tool calls(OTel) 노출.

> 자격기술 사고 폐기: 해커톤의 "3-of-3"는 더 이상 무의미. **Real-Time Search API 안 함.**
> 기술 축은 **Slack Assistant + AWS MCP** 둘로 충분(발표 서사에 깔끔). (사용자 결정 2026-06-26)

### 결정 사항 (확정)
- **데모 환경:** 실 AWS(EC2+CloudWatch via MCP) + **로컬 mock 폴백** + **사전 녹화 백업** (라이브 사고 대비).
- **검색 API:** ❌ 안 함 — AWS MCP가 외부연동 축을 대신.
- **산출물:** 라이브 데모 경로 1개 + AWSKRUG 슬라이드 + 녹화 백업.
- **재플랫폼 범위:** full Slack Assistant 재플랫폼(D1 착수됨) — slash는 폴백으로 유지.

---

## 2. 자산 인벤토리 (재사용 — 발표 데모를 빠르게 만드는 근거)

| 영역 | 자산 | 발표 데모 처리 |
|---|---|---|
| Slack | Bolt Socket Mode + `/devops` 라우팅 (`slack_handler.py`) | **재플랫폼** (slash → Assistant), slash는 폴백 |
| 추론 | Claude Code Headless + **stream-json** (`claude_runner.run_headless_stream`) | **그대로** (스트리밍 응답 토대) |
| 대화 | `chat_agent.py` 폴링 컨슈머 + 대화 버스(`chat_store.py`) | Assistant 스레드 렌더 로직 이식 |
| 보안 | 권한 L0/L1 + **4층 인젝션 방어**(sanitizer/allowlist/output gate/template) | **그대로 — 발표 핵심 차별점** |
| MCP | `aws-api-mcp-server` 연동 + 자체 FastMCP(`mcp_server.py`, propose_job) | **그대로 — 발표 핵심(agentic AWS)** |
| 관측성 | OTel span + cost/token 계측(`telemetry.py`) | 그대로 — footer 노출 |
| 큐/스토어 | 단일테이블 Job/Audit/Telemetry (sqlite+dynamodb) + worker 출력게이트 | 그대로(승인 게이트 상태머신) |
| 검증 | pytest 310 passed / ruff / mypy strict | 회귀 가드 |

**결론:** 백엔드·보안·관측성·MCP는 완성. 발표를 위해 필요한 건 **Assistant UX 마감 + 데모 시나리오/슬라이드**뿐.

---

## 3. 설계 — Slack Assistant 재플랫폼 (발표 데모의 표면)

### 목표 UX (데모 시연 흐름)
```
발표자가 Slack에서 SlackOps Assistant 패널 오픈
  → "checkout-service가 느려" (한국어 자연어, 슬래시 없음)
  → 에이전트가 스레드에서 **스트리밍**으로 진단 (AWS MCP → 실 CloudWatch) + suggested prompts
  → (인젝션 데모) 로그에 심긴 악성 지시 → 에이전트가 무시함을 보여줌
  → 위험 작업(PR 등) → diff를 스레드에 먼저 게시 → **사람 승인 버튼** → worker 실행
  → 비용/토큰/소요시간(OTel) 요약 footer
```

### 아키텍처(변경분만)
```
Slack Assistant(threads + streaming) ──┐
                                       ├─→ 기존 라우팅/권한/sanitizer/allowlist (그대로)
(폐기 아님) /devops slash = 폴백 유지 ──┘        ↓
                                       Claude Code Headless (run_headless_stream)
                                       ↓ AWS API MCP (read-only, Instance Profile)
                                       ↓ 위험 작업 → 출력게이트(diff→승인) → worker
                                       단일테이블 큐 + OTel (그대로)
```

### 구현 포인트
- `assistant_handler.py` (D1 완료): Assistant `thread_started`(인사+suggested) / `user_message`(placeholder→스트리밍 chat.update).
- 자연어 입력 → sanitizer `build_prompt`로 격리 → propose-only 도구 + (데모용) AWS MCP read 도구 주입.
- 스트리밍 = `run_headless_stream`(stream-json) → Slack `chat.update` 점진 렌더(throttle).
- 승인 게이트 = 스레드 내 Block Kit 버튼(Approve/Reject) → 기존 worker 출력게이트 상태머신 재사용.

---

## 4. 실행 계획 (대폭 축소 — 발표 데모 1경로 안정화에 집중)

> 규칙: 한 번에 하나, 변경마다 `pytest` 풀런 + 커밋. **데모 안정성 > 기능 추가.**

| 단계 | 우선 | 작업 | Done 기준 | 상태 |
|---|---|---|---|---|
| **D1** | P0 | Assistant 핸들러 스캐폴드 + 자연어 라우팅(단위테스트) | 새 테스트 green, gate 유지 | ✅ done (9460a24) |
| **D2** | P0 | 스트리밍 응답(스레드 점진 렌더) + 승인 버튼 게이트(Block Kit) 이식 | 로컬 e2e: 진단→diff→승인 | **← 다음** |
| **D3** | P0 | 데모 시나리오 확정 + **로컬 mock 폴백 경로** 안정화(네트워크 없이 재현) | mock로 풀 시연 재현 | — |
| **D4** | P0 | **실 AWS 1회 e2e**(EC2 재기동 → Assistant로 실 CloudWatch 진단 → write-denied) | 실 동작 캡처 확보 | — |
| **D5** | P0 | **사전 녹화 백업**(라이브 사고 대비) + 인젝션 방어 데모 1장면 | 녹화본 + 인젝션 시연 | — |
| **D6** | P0 | **AWSKRUG 슬라이드** (문제→아키텍처→보안/관측성→데모→교훈) | 슬라이드 초안 | — |
| 버퍼 | P1 | 리허설 + 타이밍 조정 + Q&A 대비 | 발표 리허설 1회 | — |

> 제거된 작업(해커톤 전용): Devpost 폼/제출영상/sandbox URL/테스트 접근권한/Slack Developer Program/Real-Time Search/트랙 명시/심사용 영어 서사.
> (발표가 영어가 아니면 영어화도 불필요 — 한국어 데모가 오히려 임팩트.)

---

## 5. 발표 산출물 체크리스트
- [ ] **라이브 데모 경로 1개** — Assistant 스레드 자연어 → 스트리밍 진단 → 인젝션 방어 → 승인 게이트 → footer
- [ ] **로컬 mock 폴백** — 네트워크/AWS 없이도 동일 시연 재현(현장 리스크 대비)
- [ ] **사전 녹화 백업** 영상 — 라이브 실패 시 대체
- [ ] **AWSKRUG 슬라이드** — 문제정의 → 아키텍처 → 보안(승인게이트+4층 인젝션방어) → 관측성(OTel) → 데모 → 교훈
- [ ] 아키텍처 다이어그램 — Slack Assistant 전면 (`docs/submission/architecture.*` 재활용/갱신)
- [ ] (선택) 공개 리포 정리 — 발표 후 참고용

---

## 6. 리스크 & 완화
| 리스크 | 완화 |
|---|---|
| 라이브 데모 실패(네트워크/AWS/Slack) | **로컬 mock 폴백 + 사전 녹화 백업** 2중 안전망 |
| 실 AWS 비용 | EC2 단발 기동→데모/캡처→즉시 종료 (`make cloud-*` 라이프사이클), DynamoDB는 ~$0 유지 |
| Assistant API 동작 불확실 | slash 커맨드 폴백 유지 — 최악의 경우 기존 UX로 시연 가능. 백엔드 무변경 |
| 인젝션 데모가 밋밋 | 로그에 심긴 악성 지시를 에이전트가 무시 + sanitizer `<untrusted_data>` 경계를 슬라이드로 시각화 |
| 발표 시간 초과 | 데모 1경로로 압축 + 녹화본은 2배속 편집본 준비 |

---

## 7. 부록 — 폐기된 해커톤 규정(참고용, 2026-06-26 검증)
> 자격 불가로 **사용 안 함**. 기록만 남김.
- 대회: Slack Agent Builder Challenge (Salesforce/Slack + Devpost). 마감 7/13 17:00 PT(=7/14 09:00 KST).
- 자격기술 ≥1: Slack AI capabilities / MCP server integration / real-time search API.
- 트랙: New Slack Agent / Slack Agent for Good / Slack Agent for Organizations.
- **자격 차단 사유:** §3 Eligibility Area 16개국에 한국 미포함(일본 포함). "VOID OUTSIDE OF THE ELIGIBILITY AREA."
