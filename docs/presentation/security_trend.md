# security_trend.md — 최신 AI Agent 보안 개념 ↔ SlackOps 설계 연계

> 목적: 발표에서 "이 설계가 2025~2026 최신 에이전트 보안 흐름과 어떻게 맞닿는가"를 설명·방어하기 위한 레퍼런스.
> 대상: 발표자(개념 학습) + Q&A 대비. 상세 통제 구현은 `docs/strategy.md`·`docs/suggestion.md`, 발표 대본은 `PRESENTATION.md`.
> ✅ 인용(저자·연도·arXiv)은 §6에서 웹 원문 검증 완료(2026-07-17).

## 0. 한 줄 요약
우리 설계는 **표준 프레임워크(OWASP·AWS·OpenAI)** 뿐 아니라 **2025년 프롬프트 인젝션 방어 담론의 최신 개념
(Lethal Trifecta · control/data 분리 · Plan-Then-Execute · Zero Standing Privilege)** 과도 실질적으로 일치한다.
구현은 이미 다 되어 있고, 발표에는 "이름"만 붙이면 최신성이 살아난다.

---

## 1. 표준 프레임워크 (이미 덱에 앵커됨)

| 프레임워크 | 핵심 | 우리 연계 | 덱 위치 |
| --- | --- | --- | --- |
| **OWASP Top 10 for LLM Applications 2025** | LLM01~LLM10. 중심축 **LLM06 Excessive Agency** | 10개 중 7개 직접 커버 매핑표 | S6(이론 근거) |
| **OWASP Top 10 for Agentic Applications 2026** (2025-12-09, ASI01~10) | agent 특화: Tool Misuse·Identity/Privilege Abuse·Agentic Supply Chain 등 | ASI02→command_guard, ASI03→role split, ASI04→MCP registry | S6 보조 배너 |
| **OpenAI: Designing agents to resist prompt injection** (2026) | 인젝션은 사회공학적 맥락 조작 — 입력 분류로 못 막음, source·sink 함께 축소 | source(격리)+sink(도구 0·hard deny) | S7(source/sink) |
| **AWS AI Security Framework / agentic 원칙** | 모델 '밖' 최소권한 인가 + high-consequence 사람 승인 | IAM role split + 승인 게이트 | S5·S6 |

출처: genai.owasp.org · openai.com · aws.amazon.com/blogs/security

---

## 2. 최신 개념 (이름만 붙이면 최신성↑) — 핵심 파트

### 2.1 Lethal Trifecta (치명적 3종 결합) ★ 가장 임팩트
- **개념(Simon Willison, 2025):** 에이전트가 아래 셋을 **동시에** 가지면 프롬프트 인젝션이 실제 피해로 터진다.
  ① 민감 데이터 접근  ② 비신뢰 콘텐츠 노출  ③ 외부로 통신(데이터 유출)하는 능력
- **우리 설계 = 세 다리를 각각 끊음:**
  - ① 민감 데이터 → **fixed read adapter** 로 정해진 증거만(범위 한정), Claude env 에서 secret 제거
  - ② 비신뢰 콘텐츠 → **`<untrusted_data>` 격리** + sanitizer
  - ③ 외부 통신 → **egress allowlist(Squid, 5개 도메인)** — 여기서 다리를 자름
- **발표 훅:** "앞의 둘이 뚫려도 ③번 다리가 없으면 데이터가 못 나갑니다." → egress 경계의 의미가 최신 언어로 즉시 설명됨.
- 매핑: OWASP LLM01 + LLM02.

### 2.2 Control flow / Data flow 분리 (CaMeL 계열)
- **개념(CaMeL="CApabilities for MachinE Learning", Google DeepMind & ETH Zurich, "Defeating Prompt
  Injections by Design", 2025, arXiv:2503.18813):** 신뢰된 코드가 **제어 흐름**을 쥐고,
  모델(특히 비신뢰 데이터를 본 모델)은 **데이터만** 다루게 분리. 모델이 위험 동작의 트리거가 되지 못하게 함.
- **우리 설계:** PR **execute 경로에서 LLM 을 제거** — 결정적 코드(`app.pr_execution.open_pr`, 고정 argv)가
  branch→commit→push→PR 을 수행. 모델은 "무엇을 바꿀지 제안"만 하고 "실제 실행"의 제어권은 코드가 가짐.
- 매핑: OWASP LLM05(Improper Output Handling) / ASI05(Unexpected Code Execution).

### 2.3 Plan-Then-Execute 패턴
- **개념("Design Patterns for Securing LLM Agents against Prompt Injections", 2025 — 6패턴 중 하나):**
  실행 전에 계획을 **먼저 고정**하고, 실행 중 유입되는 비신뢰 데이터가 그 계획을 못 바꾸게 한다.
- **우리 설계:** **plan-binding** = 승인 시점 계획(plan hash·도구체인·workspace·diff)을 고정 → 실행 직전 재비교,
  다르면 `plan_binding_rejected`. Plan-Then-Execute 의 **보안 강화판**(승인+TOCTOU 방어까지).
- 다른 패턴과의 관계: **Action-Selector**(fixed adapter=행동 공간 제한), **Context-Minimization**(bounded untrusted_data)도 부분 적용.
- 매핑: OWASP LLM06.

### 2.4 Zero Standing Privilege / JIT(Just-In-Time) 접근
- **개념:** 상시 권한을 두지 않고, 필요한 순간에만 최소 권한을 발급하고 즉시 회수.
- **우리 설계:** PR write = 승인마다 발급·회수되는 **단기 GitHub App 토큰**, 평소 쓰기 자격 0. AWS 측은 **STS 1h·45분 회전**.
- 매핑: ASI03(Identity & Privilege Abuse).

### 2.5 Non-Human Identity(NHI) / Workload Identity
- **개념(2025 화두):** 사람 아닌 주체(서비스·에이전트)의 신원·자격을 사람과 구분해 단기·최소권한으로 관리.
- **우리 설계:** IAM **역할 분리**(bootstrap→runtime→MCP) + **IMDS 차단** + 단기 STS. 에이전트 신원이 상시 키가 아님.
- 매핑: ASI03.

### 2.6 Human-in-the-Loop (HITL) for high-consequence actions
- **개념:** 되돌리기 어려운(고영향) 행동은 반드시 사람 승인을 끼운다 — 모든 주요 프레임워크의 공통 권고.
- **우리 설계:** 승인 게이트(diff 먼저 게시 → Approve/Reject). L2(Execute) 비활성, production/IAM/DB hard deny.

---

## 3. 최신 개념 커버리지 한눈에

| 최신 개념 | 우리 구현 | 상태 |
| --- | --- | --- |
| Lethal Trifecta 3다리 차단 | fixed adapter + untrusted 격리 + egress allowlist | ✅ 구현, ❌ 이름 미표기 |
| Control/Data flow 분리 (CaMeL) | execute 경로 LLM 제거, 결정적 코드 | ✅ 구현, △ 이름 없음 |
| Plan-Then-Execute | plan-binding (+TOCTOU 방어) | ✅ 구현 |
| Zero Standing Privilege / JIT | 단기 write 토큰, STS 회전 | ✅ 구현 |
| Non-Human Identity | role split, IMDS 차단 | ✅ 구현 (5-B) |
| HITL (high-consequence) | 승인 게이트 | ✅ 구현 |

→ **실구현은 최신 흐름과 거의 다 일치. 발표에 "이름"과 각주만 추가하면 됨.**

---

## 4. 정직한 갭 (Q&A 대비)
- **ASI06 Memory & Context Poisoning / ASI07 Insecure Inter-Agent Communication** — 단일 에이전트 구조라
  다중 에이전트 위협면은 대부분 해당 없음. 물으면 "single-agent 설계라 해당 위협면을 축소했다"고 답한다.
- **모델 공급망** — Claude 구독 사용. 모델 자체 무결성은 Anthropic 신뢰에 의존(우리 범위 밖).
- **의미론적 인젝션(격리된 데이터 내부의 미묘한 조작)** — 완전 차단 불가. tool-less L0 분석 + 권한/출력 게이트로 피해를 억제(sink 축소)한다는 게 정직한 입장.

---

## 5. 발표 반영 제안 (실행 옵션)
1. **[강력권장] "Lethal Trifecta 를 우리가 끊는다" 슬라이드 1장** 추가 — S5(런타임 보안) 또는 S7(source/sink) 인접.
   3다리(민감데이터/비신뢰콘텐츠/외부통신) → 각 다리를 끊는 우리 통제 대응. 최신성·기억성 최고.
2. **[선택] 각주 태깅** — 5-B(→NHI·JIT), S7(→Lethal Trifecta·source/sink), 교훈 슬라이드(→CaMeL·Plan-Then-Execute).
3. **선행 작업:** 위 인용(저자·연도·arXiv)을 웹으로 1회 검증한 뒤 슬라이드에 표기.

## 6. 참고 자료 (웹 원문 검증 완료 2026-07-17)
- **Lethal Trifecta:** Simon Willison, "The lethal trifecta for AI agents: private data, untrusted content,
  and external communication", 2025-06-16 — https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/
- **CaMeL:** "Defeating Prompt Injections by Design" (CaMeL = CApabilities for MachinE Learning),
  Google DeepMind & ETH Zurich, 2025 — https://arxiv.org/abs/2503.18813
- **6 Design Patterns:** "Design Patterns for Securing LLM Agents against Prompt Injections",
  Beurer-Kellner·Fischer 외 14인, 2025 — https://arxiv.org/abs/2506.08837
  (Action-Selector · Plan-Then-Execute · LLM Map-Reduce · Dual LLM · Code-Then-Execute · Context-Minimization)
- **OWASP GenAI Security Project** — LLM Top 10 2025 / Agentic Applications 2026 (ASI) — https://genai.owasp.org
- **OpenAI** — Designing agents to resist prompt injection (2026) — https://openai.com
- **AWS** — AI Security Framework / agentic 보안 원칙 — https://aws.amazon.com/blogs/security
