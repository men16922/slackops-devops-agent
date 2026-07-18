# SlackOps DevOps Agent — AWSKRUG 발표자료 재구성 프롬프트

> 상태: 최종본을 만들 때 사용한 **역사적 15장 재구성 프롬프트**다. 현재 편집 지시로 사용하지 않는다.
> 최종 정본: `docs/presentation/SlackOps.pdf`(18장), `SlackOps DevOps Agent.pptx`, `PRESENTATION.md`.
> 아래 슬라이드 번호와 편집 지시는 이전 15장 초안의 설계 기록으로 보존한다.

## 커뮤니케이션 목표

AWSKRUG DevOps 참석자가 발표를 마쳤을 때 아래 두 가지를 이해하게 한다.

1. 최근 AI Agent 보안 문제는 모델의 오답 자체보다, 오답이 도구와 권한을 통해 실제 행동이 되는 데 있다.
2. SlackOps는 모든 Agent 보안의 정답이 아니라, 동작하는 POC를 Production에 내보내기 위해 보안 경계를 구현하고 검증한 사례다.

발표의 본문 흐름은 반드시 아래 순서를 따른다.

```text
AI Agent의 범용 보안 문제
→ 글로벌 위험 지형
→ POC와 Production의 차이
→ SlackOps 구현 사례
→ 실제 통제와 거부 증거
→ 다른 Agent에도 적용할 수 있는 결론
```

표지에는 발표 제목이 있으므로 SlackOps 이름이 나온다. 다만 본문 Slide 2~4에서는 SlackOps 기능·아키텍처·스크린샷을 제시하지 않는다. SlackOps는 Slide 5에서 처음으로 "해결을 시도한 구현 사례"로 등장시킨다.

## 전체 원칙

AWS re:Invent, Google Cloud Next, Microsoft Build 자료처럼 슬라이드마다 메시지를 하나만 전한다.

- 제목은 2줄, 본문은 키워드 3묶음을 넘기지 않는다.
- 설명 문단은 화면에서 걷어내고 `PRESENTATION.md` 대본에 담는다.
- 다이어그램, 실제 Slack 화면, 대시보드, 코드 캡처가 화면의 60~70%를 차지하게 한다.
- 핵심 수치와 보안 경계는 크게, 세부 구현명은 작은 각주나 대본에 둔다.
- 흰 배경, 넓은 여백, 짙은 네이비 본문, AWS 오렌지 포인트를 일관되게 쓴다.
- 카드 테두리는 옅게 처리하고 카드 안에는 제목과 한 줄만 남긴다.
- AWS·Slack·GitHub 서비스는 공식 아이콘이나 단순한 선형 아이콘으로 구분한다.
- 스크린샷은 브라우저 전체를 쓰지 않는다. 발표 메시지에 필요한 부분만 자른다.
- 표보다 흐름도, 문장보다 키워드, 설명보다 실제 증거를 앞세운다.
- 출처는 우하단의 10~12pt 회색 각주로 통일한다.
- 현재 덱의 색상, 타이포그래피, 푸터, 페이지 번호와 AWSKRUG 발표 톤은 유지한다.
- 슬라이드 수와 순서는 15장 그대로 유지한다. 새 슬라이드를 추가하거나 기존 슬라이드를 삭제하지 않는다.
- Slide 2~5는 서사에 맞게 전면 재구성하고, Slide 6~15는 기존 증거 자산을 최대한 보존한다.

## 공통 타이포그래피

- 슬라이드 제목은 36~44pt 굵은 글씨로 쓴다.
- 핵심 문장과 수치는 28~36pt로 키운다.
- 카드 제목은 18~22pt, 본문 키워드는 16~20pt로 맞춘다.
- 각주는 10~12pt를 사용한다.
- 카드 하나에는 3줄까지만 허용한다.

---

## [수정] Slide 1/15 — 표지

다크 네이비 배경과 오렌지 포인트는 그대로 살린다.

화면에는 아래 내용만 남긴다.

```text
SlackOps DevOps Agent
보안팀도 승인할 수 있는 AI 운영 에이전트

최병민 · 현대오토에버
AWSKRUG DevOps · 2026.07.23
```

- `Security-first · Human-in-the-loop · Fully instrumented` 배지는 최대 2개만 남긴다.
- 우측 하단 장식을 덜어내고 제목 주변에 여백을 확보한다.

---

## [전면 재설계] Slide 2/15 — AI Agent는 답변이 아니라 행동을 만듭니다

기존 SlackOps 캡처와 온콜 상황은 제거한다. 특정 제품이나 DevOps 사례를 보여주지 말고, 챗봇과 Agent의 보안 차이를 범용적으로 설명한다.

```text
AI Agent = 판단 + 도구 + 권한

챗봇의 오답 → 잘못된 정보
에이전트의 오답 → 실제 행동

문제는 오답이 아니라 오답의 실행권입니다
```

- 화면을 `CHATBOT`과 `AGENT` 두 영역으로 나눈다.
- `CHATBOT`은 `Prompt → Response`까지만 연결한다.
- `AGENT`는 `Goal → Reason → Tool → System`으로 연결하고, `Tool → System` 화살표만 경고색으로 강조한다.
- 사람·로봇 일러스트보다 데이터와 실행 흐름이 보이는 단순한 선형 시각화를 우선한다.
- SlackOps, AWS, CloudWatch, Slack 로고와 실제 제품 캡처는 넣지 않는다.
- 우하단 각주: `OpenAI, Designing AI agents to resist prompt injection, 2026-03-11`.

---

## [전면 재설계] Slide 3/15 — 글로벌 이슈는 Agent 생태계 전체로 확장됐습니다

기존 `Slack 요청 → AI 진단 → 사람 승인` 흐름은 제거한다. OWASP Top 10 for Agentic Applications 2026의 전체 위험 지형을 세 묶음으로 보여준다.

```text
GOAL & CONTEXT
Goal Hijack · Memory & Context Poisoning

TOOLS & IDENTITY
Tool Misuse · Privilege Abuse · Unexpected Code Execution

ECOSYSTEM & OPERATIONS
Supply Chain · Inter-Agent · Cascading Failure · Rogue Agent · Human Trust
```

- 세 묶음은 서로 분리된 카드 모음보다 왼쪽에서 오른쪽으로 위험 범위가 확장되는 하나의 흐름으로 표현한다.
- `GOAL & CONTEXT`는 비신뢰 입력, `TOOLS & IDENTITY`는 실제 실행권, `ECOSYSTEM & OPERATIONS`는 연결된 Agent와 운영 확산을 의미하게 한다.
- 열 개 항목을 각각 설명하지 않는다. 묶음 제목과 대표 위험만 읽히게 하고 세부 내용은 대본으로 넘긴다.
- 특정 벤더 로고와 SlackOps 구현은 넣지 않는다.
- 하단 각주: `OWASP Top 10 for Agentic Applications 2026 · ASI01–ASI10`.

---

## [전면 재설계] Slide 4/15 — POC가 되는 것과 Production에 내보내는 것은 다릅니다

기존 Safe-Autonomy Loop는 제거한다. 왼쪽의 POC 질문과 오른쪽의 Production 질문을 대비한다.

```text
POC                         PRODUCTION
Can it do the task?         What can it read?
                            What can it execute?
                            Whose authority does it use?
                            Can we stop and audit it?

속아도 안전한 운영 에이전트를 만들 수 있을까?
```

- `POC` 영역은 작고 단순하게, `PRODUCTION` 영역은 더 넓고 무겁게 표현한다.
- Production의 네 질문은 `READ · EXECUTE · AUTHORITY · AUDIT` 키워드와 아이콘으로 정리한다.
- 하단 질문은 발표자의 프로젝트 출발점이므로 가장 크게 보이게 한다.
- SlackOps 이름과 아키텍처는 아직 넣지 않는다.
- 작은 각주: `Least agency · Independent authorization · Human approval · Auditability`.

---

## [전면 재설계] Slide 5/15 — 이 질문을 검증하기 위해 SlackOps를 만들었습니다

이 슬라이드에서 SlackOps를 처음으로 구현 사례로 공개한다. 범용 문제에서 프로젝트로 넘어가는 전환이 분명해야 한다.

- `docs/presentation/Architecture.png`를 화면 중앙에 크게 쓴다.
- 다이어그램을 다시 설명하는 문장은 넣지 않는다.
- 상단이나 좌측에는 아래 3개 키워드만 둔다.

```text
MULTIPLE INPUTS
READ-ONLY TRIAGE
HUMAN-BOUND CHANGE
```

- 제목 아래 작은 문장: `POC를 Production 경계 안으로 옮겨 본 구현 사례`.
- 아키텍처 이미지의 불필요한 여백을 잘라 작은 화면에서도 읽히게 한다.
- 세부 흐름과 역할 분리는 `PRESENTATION.md` Slide 5에서 말한다.
- 제품 소개나 기능 목록처럼 보이지 않게 한다. 앞 슬라이드의 Production 질문에 답하기 위한 구조라는 점이 우선이다.

---

## [수정] Slide 6/15 — 첫 원칙은 모델을 보안 경계로 사용하지 않는 것입니다

현재 3개 카드의 설명 문단을 걷어내고 아이콘과 키워드만 남긴다.

```text
IDENTITY SPLIT
Bootstrap-only · Runtime / MCP / Audit

SHORT-LIVED STS
1h expiry · 45m rotation · IMDS blocked

EGRESS ALLOWLIST
Slack · Claude · GitHub · AWS · Terraform
```

- 카드마다 방패, 시계, 네트워크 아이콘을 하나씩 붙인다.
- 하단은 아래 문장 하나만 크게 보여준다.

```text
상시 권한은 두지 않는다.
자격 증명은 짧게 쓰고, 외부 통신은 필요한 곳만 허용한다.
```

- 작은 각주: `OWASP ASI03 · LLM02 · Zero Standing Privilege / JIT credentials`.

---

## [수정] Slide 7/15 — 요청에서 제안까지

실제 Slack 요청과 diff 캡처가 화면의 65% 이상을 차지하게 한다.

좌측에는 아래 증거 배지 3개만 둔다.

```text
FIXED READ ADAPTER
L0 TOOLS = 0
$0.15 / RUN
```

- `Slack 요청 → CloudWatch 증거 → 진단 → PR 제안`은 한 줄 화살표로 연결한다.
- 실행 상태와 토큰, 비용은 대본에서 설명한다.
- 작은 글씨가 보이지 않으면 핵심 메시지와 diff를 따로 잘라 2개 패널로 만든다.

---

## [수정] Slide 8/15 — 승인 게이트

현재 캡처에서 승인 영역과 diff만 읽히도록 확대한다.

```text
PROPOSE  →  REVIEW  →  APPROVE  →  EXECUTE
```

- `APPROVE`에만 오렌지 테두리를 쓴다.
- 설명은 아래 한 줄로 충분하다.

```text
승인한 내용 그대로만 실행한다
```

- 작은 각주: `Plan-Then-Execute · TOCTOU defense`.

---

## [수정] Slide 9/15 — 하나의 작업 큐

Job Queue 대시보드를 크게 쓰고 좌측 설명은 3개 키워드로 끝낸다.

```text
SINGLE TABLE
CONDITIONAL CLAIM
AUDIT + TELEMETRY
```

- `Slack · Vercel · Agent · Event-driven Lambda`는 작은 source 배지로 묶는다.
- 비동기 처리와 중복 실행 방지, 비용 기록은 대본으로 넘긴다.

---

## [전면 재설계] Slide 10/15 — Lethal Trifecta와 최소 권한

현재의 설명 카드 5개는 없앤다. 대신 3개의 다리로 보안 경계를 보여준다.

제목:

```text
세 다리를 동시에 주지 않는다
```

중앙 시각화:

```text
PRIVATE DATA
Fixed read adapter
        ✕
UNTRUSTED CONTENT
<untrusted_data> isolation
        ✕
EXTERNAL COMMUNICATION
Squid egress allowlist
```

- 3개 요소는 삼각형이나 3-leg 다이어그램으로 연결한다.
- `EXTERNAL COMMUNICATION` 차단이 가장 먼저 보이게 한다.
- 우측이나 하단에는 아래 보안 배지 3개만 놓는다.

```text
L0 TOOLS = 0
SHORT-LIVED STS
NO STANDING WRITE CREDENTIAL
```

- 하단 standards rail에는 `OWASP ASI01 · ASI02 · ASI03 · ASI05`만 적는다.
- 각주는 `Simon Willison, “The lethal trifecta for AI agents”, 2025-06-16`으로 표기한다.
- Slide 10에서는 세 가지 위험 요소와 경계만 보여준다. 세부 OWASP 매핑은 Slide 14에서 구현 증거와 함께 보여준다.

---

## [수정] Slide 11/15 — Detections & Telemetry

대시보드 2개는 유지한다. 상단 설명 대신 핵심 수치 3개를 크게 뽑는다.

```text
RUNS
TOKENS
COST
```

- 현재 캡처의 실제 숫자를 KPI 타일로 확대하는 방식을 우선한다.
- 하단 작은 배지에는 `INFRA ~$12/mo`와 `CLAUDE $0.15~$0.50/run`을 넣는다.
- 관측 항목과 비용 산정 과정은 대본에 둔다.

---

## [수정] Slide 12/15 — 보안 증명

거부 화면과 plan-binding 화면은 그대로 쓴다. 설명은 두 개의 증거 배지로 압축한다.

```text
READ-ONLY DENIED
PLAN BINDING REJECTED
```

- 좌측에는 `restart · apply · delete → DENY`만 남긴다.
- 우측에는 `plan hash · tool chain · workspace · PR diff → RECHECK`만 남긴다.
- 아래 문장이 화면의 결론이 되게 한다.

```text
승인 후 한 글자라도 바뀌면 실행하지 않는다
```

- 검증 상태는 작은 칩 3개로 구분한다.
  - `EC2 경계 · 실환경 검증`
  - `GitHub App · 실제 PR 검증`
  - `Managed MCP · 미사용`

---

## [수정] Slide 13/15 — 라이브 데모 전환

다크 화면은 유지하고 아래 문구 외에는 모두 지운다.

```text
LIVE
Slack → Diagnose → Approve → PR
```

- 우측 불릿은 없앤다.
- 중앙의 `LIVE`와 빨간 점이 시선을 잡게 한다.
- 시연 순서와 실패 시 대안은 `PRESENTATION.md` Slide 13에서 확인한다.

---

## [수정] Slide 14/15 — SlackOps는 글로벌 위험을 운영 통제로 번역한 사례입니다

설계 교훈 카드 5개를 없애고 `위험 → 구현 → 증명` 한 장으로 바꾼다. 표처럼 빽빽하게 그리지 말고, 왼쪽에서 오른쪽으로 읽히는 가로 연결선 5개를 사용한다.

```text
위험                         구현                              증명
ASI01 Agent Goal Hijack      <untrusted_data> · L0 tools=0    악성 목표의 실행 차단
ASI02 Tool Misuse            fixed adapter · command_guard    미허용 argv 거부
ASI03 Identity Abuse         role split · JIT write token     상시 write 권한 0
ASI05 Unexpected Execution   deterministic executor · hash    변경된 계획 거부
ASI09 Human-Agent Trust      diff review · approver identity  승인 주체·대상 추적
```

- 위험 열은 연한 주황, 구현 열은 AWS 블루, 증명 열은 초록으로 구분한다.
- 각 행은 아이콘 1개, 키워드 2개 이하, 증명 문구 1개만 둔다.
- 영어 OWASP 항목명은 작게, 한국어 증명 문구는 가장 크게 보이게 한다.
- 별도 설명 문단과 장식용 카드는 넣지 않는다.
- 하단에는 `OWASP Top 10 for Agentic Applications 2026 · 실제 적용 범위만 매핑`만 작게 적는다.
- 세부 구현과 검증 범위는 `PRESENTATION.md` Slide 14 대본에서 설명한다.

---

## [수정] Slide 15/15 — Production의 기준은 통제 가능한 행동입니다

다크 네이비 배경은 살리고 해커톤 푸터는 지운다.

```text
Production의 기준은
더 똑똑한 모델이 아니라 통제 가능한 행동입니다

AI는 조사하고 제안합니다
사람은 diff를 검토하고 결정합니다

github.com/men16922/slackops-devops-agent
최병민 · 현대오토에버 · 2026.07.23
```

- `통제 가능한 행동`을 오렌지로 강조해 Slide 2의 `오답의 실행권` 문제를 회수한다.
- 우측 세로 인포그래픽은 `docs/presentation/simple.png`로 바꾼다.
- 인포그래픽이 본문을 압도하면 크기를 줄이고 여백을 넓힌다.
- `지금 바로 시작해 보세요!` 문장은 삭제한다.

---

## 발표자 대본으로 옮길 내용

아래 내용은 슬라이드에 쓰지 않는다. `PRESENTATION.md` 대본에서 설명한다.

- Slide 2에서는 Agent가 외부 데이터를 읽는 source와 실제 행동을 수행하는 sink를 연결한다는 점을 말로 설명한다.
- Slide 3에서는 OWASP ASI01~ASI10의 정확한 명칭과 세부 정의를 화면에 모두 쓰지 않는다.
- Slide 4에서는 POC의 단발 성공보다 반복 가능한 제한·승인·감사 증명이 Production의 기준이라는 점을 설명한다.
- Instance Profile은 bootstrap에만 쓰고 runtime/MCP/audit 역할을 나눈다.
- STS 자격은 1h 뒤 만료하고 45분마다 회전한다. AI 프로세스의 IMDS 직접 접근도 막는다.
- fixed read adapter가 증거를 가져오며 L0 tool allowlist는 0이다.
- `<untrusted_data>` 격리와 sanitizer는 외부 입력을 명령이 아닌 데이터로 다룬다.
- 승인 시 저장한 plan hash, tool chain, workspace, PR diff를 실행 직전에 다시 확인한다.
- GitHub App write token은 승인마다 발급하고 실행이 끝나면 회수한다.
- capability drift가 발견된 작업은 완료 처리하지 않는다.
- Managed MCP는 현재 런타임에 연결하지 않았다. 별도 계정 파일럿을 위한 설계와 CI 검증 코드만 있다.
- OWASP 항목별 구현과 실증 범위는 Slide 14 대본에서 설명한다.

## 인용 정본

- **Lethal Trifecta:** Simon Willison, "The lethal trifecta for AI agents: private data, untrusted
  content, and external communication", 2025-06-16 — simonwillison.net/2025/Jun/16/the-lethal-trifecta/
- **CaMeL:** "Defeating Prompt Injections by Design", **Google DeepMind & ETH Zurich**(Debenedetti,
  Tramèr 등), 2025, arXiv:2503.18813. CaMeL = "CApabilities for MachinE Learning".
- **6 Design Patterns:** "Design Patterns for Securing LLM Agents against Prompt Injections",
  Beurer-Kellner·Fischer 외 14인, 2025, arXiv:2506.08837.
- **OWASP:** "Top 10 for Agentic Applications 2026" — https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/
- **OpenAI:** "Designing AI agents to resist prompt injection", 2026-03-11 — https://openai.com/index/designing-agents-to-resist-prompt-injection/
- **AWS:** "The Agentic AI Security Scoping Matrix", 2025-11-21 — https://aws.amazon.com/blogs/security/the-agentic-ai-security-scoping-matrix-a-framework-for-securing-autonomous-ai-systems/
- **AWS:** "The AWS AI Security Framework", 2026-05-15 — https://aws.amazon.com/blogs/security/the-aws-ai-security-framework-securing-ai-with-the-right-controls-at-the-right-layers-at-the-right-phases/

## 최종 검수 기준

- 아래 15장 검수 항목은 설계 당시 기준이다. 최종 18장은 `SlackOps.pdf`와 `PRESENTATION.md`로 검수한다.
- 슬라이드마다 핵심 메시지가 하나만 남는다.
- 발표자가 말할 설명 문단은 화면에 남지 않는다.
- 프로젝터에서도 핵심 키워드와 캡처가 읽힌다.
- `Architecture.png`, `simple.png`, 실제 Slack·대시보드 캡처가 선명하다.
- 모든 수치와 검증 상태가 `PRESENTATION.md`와 같다.
- Slide 2~4에는 SlackOps 기능, 구현, 로고, 제품 캡처가 없다.
- Slide 4에서 POC와 Production의 차이가 한눈에 읽힌다.
- Slide 5에서 SlackOps가 제품 소개가 아니라 앞 질문을 검증한 사례로 등장한다.
- 최종본에서는 Slide 17이 Slide 3의 글로벌 위험을 구현·증거와 연결한다.
- 최종본에서는 Slide 18이 Slide 2의 문제를 `통제 가능한 행동`이라는 결론으로 회수한다.
