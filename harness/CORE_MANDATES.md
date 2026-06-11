# CORE_MANDATES — slackops-devops-agent
최종 갱신: 2026-06-11

> 느리게 변하는 불변 표준만. 현재 작업 맥락은 CONTEXT_BRIDGE.md / docs/ 로.

## 1. Runtime Principles
- 언어: Python 3.11+. **EC2 상주 단일 서비스**(Lambda/서버리스 아님).
- Slack: **Bolt Socket Mode**. 인바운드 HTTP 엔드포인트/공개 HTTPS/ALB/인증서 **금지**.
- LLM 실행: **Claude Code Headless**(subprocess) 호출. 직접 모델 SDK 래퍼(Bedrock/OpenAI) 생성 금지.
- Job queue: **SQLite (MVP 한정)**. prod 데이터스토어로 호칭 금지.
- 레이어: slack_handler / permissions / sanitizer / claude_runner / telemetry / commands 분리.

## 2. Security (차별화 — 엄격)
- **IAM Instance Profile 만.** Access Key 저장/커밋 절대 금지.
- 최소 권한·읽기 전용 기본: CloudWatch RO, Logs RO, EKS Describe, SSM Read, S3 Read.
- Permission Engine Level 0/1/2. **MVP 는 0·1 만 활성, 2(Execute) 비활성.**
- 금지 불변: Production 변경, 배포(apply/deploy), IAM 변경, DB 변경.
- GitHub: GitHub App 최소 스코프 + branch protection(에이전트 PR 자동 머지 차단).
- Prompt Injection 4계층: ① Context Sanitizer(`<untrusted_data>` 격리) ② Tool Allowlist(명령별)
  ③ 출력 게이트(L1 쓰기는 diff Slack 선게시 후 사람 확인) ④ Template Prompt 강제(Slack 입력 직접 전달 금지).

## 3. Observability
- OTel SDK → ADOT Collector → CloudWatch. 실행 1건당 step latency / 토큰 / 비용(USD) /
  tool call 횟수·종류·실패율 / E2E p50·p95 계측.

## 4. Cost / Ops
- EC2 는 EventBridge 스케줄 stop/start. 상시 가동 금지.

## 5. Code & Test Discipline
- 타입 힌트 필수, `from __future__ import annotations`, `X | None`.
- 로깅 structlog(또는 OTel 연동 logger). `print` 금지. bare `except`/`except: pass` 금지.
- 멀티파일 변경 후 `pytest` 전체 실행, pass/fail 보고. 통과 전 "완료" 선언 금지.
- 새 의존성은 `pyproject.toml` 먼저 확인.

## 6. Documentation & Handoff
- Read Path: CONTEXT_BRIDGE → AGENT_BRIEF → STATUS → NEXT_PLAN → (필요 시) PROGRESS_LOG.
- docs/ bulk-read 금지. current doc 갱신은 /checkpoint, 읽기는 /sync, 정리는 /tidy-docs.
- 새 글로벌(불변) 규칙은 이 파일에. 추측 금지(없으면 "문서에 없음").
- 한국어 본문 + 영어 식별자/명령/경로.
