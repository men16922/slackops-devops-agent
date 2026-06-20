# Plan — Web dashboard UI → English (H0 submission)

최종 갱신: 2026-06-20
권위: NEXT_PLAN > 이 문서. 관련: 에이전트 Slack/chat 응답은 이미 영어화 완료(이 세션, src/app/*).

## Context (왜)
H0 제출 영상에 web 대시보드가 노출되므로(심사위원 = 영어 기준) **에이전트 응답뿐 아니라 web UI 텍스트도 영어**여야 한다. 현재 `web/` 의 사용자 대면 렌더 텍스트·토스트 메시지·placeholder 가 한국어다. 코드/식별자/CSS 클래스명/단일테이블 계약은 건드리지 않는다.

## 범위 (Scope)
**대상 = 사용자에게 렌더되는 문자열만** (JSX 텍스트, return/toast 메시지, placeholder, aria-label, 버튼 라벨).
**제외 = 코드 주석**(Markdown.tsx/globals.css/Chat.tsx/lib/* 의 `//`·`/* */` 한국어 주석 — 내부용, 선택 정리). 식별자·className·DynamoDB 키·`mono` 코드 예시(`api 5xx ...`)는 그대로 둘지 검토(예시는 영어화 권장).

소스 오브 트루스(실행 전 재확인):
```sh
cd web && grep -rnE "[가-힣]" app lib | grep -vE "node_modules|\.next"
```

## 변경 대상 파일 + 문자열 매핑 (user-facing)

### app/page.tsx (홈/Job Queue)
- L16 "에이전트와 대화해 작업을 제안받고(아래 채팅), 승인하면 Slack/Web 공유 큐로 실행됩니다 (GSI2 FEED)."
  → "Chat with the agent to get job proposals (below); approve them to run on the shared Slack/Web queue (GSI2 FEED)."
- L25 "작업이 없습니다. 시드가 실행됐는지(seed 컨테이너) 또는 DynamoDB 연결을 확인하세요."
  → "No jobs. Check that the seed ran (seed container) or the DynamoDB connection."

### app/Chat.tsx (대화형 producer)
- L105 "전송 실패" → "Send failed"
- L108 "전송 중 오류가 발생했습니다." → "An error occurred while sending."
- L119 "＋ 새 대화" → "＋ New conversation"
- L126-127 "운영 에이전트와 대화하세요. 예: …api 5xx 늘었어, 원인 봐줘… · …checkout 타임아웃 올리는 PR 준비해줘…"
  → "Chat with the ops agent. e.g. `api 5xx is rising, find the cause` · `prepare a PR to raise the checkout timeout`"
- L129 "에이전트가 필요하다 판단하고…아래 Job Queue 에서 승인/거절합니다."
  → "When the agent decides it's warranted, it proposes a job; approve/reject it in the Job Queue below."
- L149 "에이전트 응답 중…" → "Agent is responding…"
- L155 "🤖 작업이 제안되었습니다 —" → "🤖 A job has been proposed —"
- L157 "Job Queue 에서 승인/거절 →" → "Approve/reject in the Job Queue →"
- L167 placeholder "에이전트 응답을 기다리는 중…" / "메시지를 입력…(Enter 전송, Shift+Enter 줄바꿈)"
  → "Waiting for the agent…" / "Type a message… (Enter to send, Shift+Enter for newline)"
- L176 aria-label "대화 입력" → "Chat input"
- L183 "전송 중…" → "Sending…"

### app/jobs/[id]/page.tsx (Job 상세 / Output Gate)
- L34 "🤖 에이전트 자율 제안" → "🤖 Autonomous agent proposal"
- L37 "운영 에이전트가 시스템을 관찰하고 이 작업을 제안했습니다. 실행은 사람 승인 후에만 진행됩니다."
  → "The ops agent observed the system and proposed this job. It runs only after human approval."
- L86 "Output Gate — 승인 필요" → "Output Gate — approval required"
- L97 "감사 이벤트 없음." → "No audit events."

### app/jobs/[id]/ApprovalButtons.tsx
- L26 "처리 중…" → "Processing…" (Approve 버튼 pending 라벨)
- (Reject 버튼에 동일 패턴 있으면 함께)

### app/metrics/page.tsx
- L50 "OpenTelemetry 계측 결과 (최근 2일, GSI2 METRIC#yyyymmdd)."
  → "OpenTelemetry metrics (last 2 days, GSI2 METRIC#yyyymmdd)."
- L79, L113 "계측 데이터 없음." → "No metrics data."

### app/actions.ts (enqueue server action 반환 메시지)
- L56 "이미 처리된 작업입니다(승인 대기 상태가 아님)." → "Job already handled (not awaiting approval)."
- L106 "허용되지 않은 명령입니다: ${command}" → "Command not allowed: ${command}"
- L109 "'${command}' 는 인자가 필요합니다 (예: 서비스명/설명)." → "'${command}' requires an argument (e.g. service name / description)."
- L112 "인자가 너무 깁니다(최대 ${ARGS_MAX}자)." → "Argument too long (max ${ARGS_MAX} chars)."
- L140 "큐에 추가됨: ${command}" → "Queued: ${command}"

### app/chat-actions.ts (chat server action 반환 메시지)
- L55 "메시지가 비어 있습니다." → "Message is empty."
- L57 "메시지가 너무 깁니다(최대 ${CONTENT_MAX}자)." → "Message too long (max ${CONTENT_MAX} chars)."
- L91 "대화를 찾을 수 없습니다 — 새 대화를 시작합니다." → "Conversation not found — starting a new one."
- L93 "지금은 에이전트가 응답 중입니다. 잠시 후 다시." → "The agent is responding right now. Try again shortly."

### lib/*.ts (확인 필요)
- lib/{time,types,ddb,format}.ts 는 grep 상 한국어 = **주석으로 추정**(렌더 안 됨). 실행 시 각 파일 확인 → 주석이면 제외(선택), 사용자 대면 문자열이면 위 패턴으로 영어화.

## 비-목표
- 코드 주석 영어화는 선택(별도). DynamoDB 키/`className`/식별자/`mono` 코드 토큰 변경 금지(예시 문구는 영어화 OK).
- 에이전트 런타임 응답(src/app/*)은 이미 영어 — 범위 밖.

## 검증
1. `cd web && npm run build`(또는 docker compose build) — Next.js TS strict green.
2. docker compose up → Playwright 로 `/`, `/jobs/<awaiting_approval>`, `/metrics` 스냅샷 → 렌더 텍스트에 한국어 0.
3. 잔여 확인: `grep -rnE "[가-힣]" web/app` 결과가 주석만 남는지(또는 0) 확인.
4. (선택) chat producer 입력→제안 흐름 1회 — 토스트/placeholder 영어 확인.

## 실행 순서
- Phase 1: app/ 사용자 대면 문자열 8개 파일 영어화(위 매핑).
- Phase 2: lib/* 한국어가 주석인지 확인 → 사용자 대면이면 영어화.
- Phase 3: build + Playwright 검증 → 커밋(에이전트 영어 응답 변경분과 함께 또는 별도).
