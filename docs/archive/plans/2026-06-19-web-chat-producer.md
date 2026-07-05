# 설계 — Web Chat Producer (Claude 대화 → job 제안, DynamoDB 메시지 버스)

작성: 2026-06-19 · 상태: 설계(미구현) · 권위: 이 문서 > 구현 중 즉흥 결정

## 1. 목표 / 제약
- **목표:** Job Queue 상단의 selectbox producer 를 제거하고, **자연어로 Claude 와 (시각적) 스트리밍 대화 →
  Claude 가 최종적으로 해야 할 작업을 `propose_job` 으로 큐에 제안 → 사람이 승인/거절**.
- **핵심 제약(반드시 충족):**
  - **배포(Vercel + EC2 + DynamoDB)에서 동작** — 로컬 전용 금지.
  - **에이전트 인바운드 포트 0 / Socket Mode 유지** — 보안 차별화(심사 포인트). web→agent 직접 HTTP 금지.
  - **구독 OAuth / Claude Code Headless subprocess** — API key·직접 SDK 래퍼 금지(D6, CORE_MANDATES §1).
  - **Template Prompt + 주입 방어** — 사용자 자유텍스트를 Claude 에 직접 전달 금지(sanitizer 격리).
  - **출력 게이트** — 실제 실행은 사람 승인 후(기존 worker 게이트 재사용).

## 2. 아키텍처 — DynamoDB 를 비동기 메시지 버스로
```
브라우저 ──(user turn write)──▶ DynamoDB  ◀──poll── EC2 에이전트(chat poller, outbound-only)
   ▲ poll(~700ms)                  │                         │ claude -p --output-format stream-json
   └──(assistant 청크 read)────────┘                         │ + sanitizer(template) + propose_job MCP
                                    └──(청크 append)◀─────────┘
                          최종 propose_job ──▶ Job Queue(PENDING/agent) ──▶ 승인/거절(기존 게이트)
```
에이전트는 **DynamoDB 를 폴링(outbound)** 하므로 인바운드 0 유지 — *"DynamoDB 가 두 control plane 의 비동기
버스"* 스토리를 강화(심사 DB축). web 은 DynamoDB 만 읽고 쓰므로 **Vercel 에서 그대로 동작**(claude 불필요).
에이전트(EC2)는 데모/녹화 시 가동, idle 시 stop — diagnose/pr 과 **동일 모델**.

## 3. 데이터 모델 (단일테이블 — JOB#/AUDIT# 규약과 일관, **새 GSI 불필요**)
대화는 item collection `PK=CHAT#{conv_id}` 로 묶는다(Job 의 JOB#{id}/META·AUDIT# 패턴과 동형):

| 항목 | PK | SK | 주요 속성 | GSI |
| --- | --- | --- | --- | --- |
| 대화 메타 | `CHAT#{conv}` | `META` | status(open\|awaiting_agent\|streaming\|done), session_id, proposed_job_id, created/updated | **GSI1PK=`CHATSTATUS#{status}`** (에이전트 claim용 — 기존 GSI1 오버로딩), GSI2PK=`CHATFEED`(목록) |
| 메시지 | `CHAT#{conv}` | `MSG#{seq:06d}` | role(user\|assistant), content, done(bool) | — |

- **GSI1 오버로딩:** Job 은 `STATUS#{status}`, 대화는 `CHATSTATUS#{status}` — 같은 GSI1, 다른 파티션.
  → `create-table.sh` 스키마 **변경 없음**(GSI1PK 는 범용 문자열). 단일테이블·GSI 오버로딩 = 강한 on-thesis.
- **스트리밍:** assistant 메시지 item 의 `content` 를 에이전트가 `UpdateItem`(SET content = content + :chunk)
  으로 **append**, `done=false`→완료 시 `true`. web 은 `Query(PK=CHAT#{conv}, SK begins_with MSG#)` 폴링 →
  자라나는 assistant 메시지를 Markdown 렌더(§web). **청크는 토큰단위 아님** — ~500ms/40토큰 배치(write 증폭 방지).

## 4. 구현 컴포넌트
1. **store/chat (신규)** — `ChatStore` 프로토콜 + Sqlite/DynamoDb 구현(기존 store 패턴·_util 재사용, moto 동치 테스트).
   메서드: `create_conversation`, `append_user_message`(→status=awaiting_agent), `claim_conversation`(GSI1
   CHATSTATUS#awaiting_agent → streaming, ConditionExpression 원자), `append_assistant_chunk`, `finish_turn`
   (→open/done), `list_messages`, `get_conversation`.
2. **claude_runner 스트리밍 (확장)** — `run_headless_stream(prompt, allowed_tools, mcp_config, on_chunk)` —
   `--output-format stream-json` 으로 claude 실행, JSONL 이벤트 파싱, 텍스트 델타를 `on_chunk` 콜백으로.
   기존 `build_command` 에 stream 분기 추가(`--output-format stream-json`). 멀티턴 컨텍스트는 대화 메타의
   `session_id` 로 `--resume`(헤드리스+mcp-config 동작 1회 스모크 필수) 또는 저장 메시지로 프롬프트 재구성(폴백).
3. **chat 에이전트 poller (신규 `src/app/chat_agent.py`)** — worker 와 형제. GSI1 CHATSTATUS#awaiting_agent
   폴링 → claim → **sanitizer.build_prompt(CHAT_TEMPLATE, user_text)** 로 격리(주입 방어/template) →
   `run_headless_stream`(allowedTools=`mcp__slackops__propose_job`만 = read-only, 직접 실행 도구 없음) →
   청크 append → Claude 가 propose_job 호출 시 기존 `propose_job_impl` 로 PENDING/agent 적재 +
   대화 메타에 `proposed_job_id` 링크 → finish_turn. 예외 격리(루프 생존).
4. **web producer UI (NewCommand 대체)** — 클라이언트 컴포넌트: 입력창 + 메시지 리스트, `append_user_message`
   server action, 메시지 ~700ms 폴링(자라나는 assistant 메시지 = Markdown.tsx 재사용), propose_job 발생 시
   **"🤖 제안됨 → Job Queue"** 콜아웃(proposed_job_id 링크). lib/ddb 에 chat 읽기/쓰기(GSI1/Query) 미러.
5. **배선** — `make chat-agent`(worker 처럼, 로컬은 호스트 claude+토큰). deploy: EC2 user-data 에 chat_agent
   systemd(worker 와 동일 패턴). web 은 변경 불필요(DynamoDB만).
6. **(선택 v2) Vercel SSE 브리지** — Vercel route 가 DynamoDB 폴링 → 브라우저 SSE 1개 연결(클라 폴링 제거).
   Vercel 함수 실행시간 제한 고려. v1(클라 폴링) 먼저.

## 5. 만다린 준수 체크
- 에이전트 outbound-only(DynamoDB 폴링) → **인바운드 0 / Socket Mode 유지** ✅
- 사용자 텍스트 = `<untrusted_data>` 격리 + 신뢰 template + allowedTools=propose_job 만(read-only) ✅
- 실행은 propose_job → **기존 출력 게이트**(사람 승인) ✅
- claude CLI subprocess + 구독 OAuth, API key 없음 ✅
- web 은 DynamoDB 만 → **Vercel 동작** ✅

## 6. 빌드 단계 (증분, 각 단계 `make check` green)
1. ChatStore 스키마 + 테스트(Sqlite+DDB moto).
2. claude_runner `run_headless_stream`(stream-json 파싱) + 스모크.
3. chat_agent poller(claim→stream→append→propose_job) + 테스트(mock runner).
4. web chat UI(NewCommand 대체) + lib/ddb chat 질의 + 폴링.
5. 배선(make chat-agent / docker-compose 또는 호스트 실행) + 로컬 e2e(Playwright).
6. (선택) Vercel SSE 브리지.
7. QA_LIST/USER_GUIDE/runbook/STATUS 갱신 + 커밋.

## 7. 리스크 / 결정 필요
- **멀티턴 컨텍스트:** `--resume <session_id>`(헤드리스+mcp 동작 확인 필요) vs 저장 메시지로 프롬프트 재구성.
  → 1단계에서 claude `--resume` 헤드리스 스모크로 결정.
- **스트리밍 충실도:** v1 폴링(~700ms 청크) — 토큰단위 아님. 충분치 않으면 v2 SSE 브리지.
- **DynamoDB write 증폭:** 청크 배치 append(per-token 금지).
- **비용:** 대화 턴당 실 Claude 호출($). 데모 한정 — chat 에이전트는 idle 시 미가동.
- **데모 의존:** chat 동작엔 EC2 chat_agent(또는 로컬 호스트) 가동 필요 — 다른 에이전트 기능과 동일.
- **selectbox 제거 영향:** 기존 `enqueueJob`(web producer) 테스트/문서 갱신. 직접 명령 적재 경로를 남길지(폴백)
  아니면 완전 chat 전환할지 → 데모 단순성 위해 **chat 단일화 권장**(필요시 ping 등 빠른 명령은 chat 로 표현).
