# SlackOps DevOps Agent V2 슬라이드 수정 프롬프트

> 기준 문서: `docs/presentation/SlackOps DevOps Agent V2.pptx` — 현재 15장.
> 슬라이드 번호는 이 PPTX의 페이지 번호를 따른다.
> 발표 내용과 용어 설명은 `PRESENTATION.md` 대본을 기준으로 한다.

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
AI가 진단하고, 변경은 사람이 승인합니다

AWSKRUG DevOps · 2026.07
```

- `Security-first · Human-in-the-loop · Fully instrumented` 배지는 최대 2개만 남긴다.
- 우측 하단 장식을 덜어내고 제목 주변에 여백을 확보한다.

---

## [수정] Slide 2/15 — 문제

CloudWatch 알람 화면은 핵심 영역만 크게 잘라 쓴다. 텍스트는 아래 3개 키워드로 끝낸다.

```text
새벽 2시, 알람이 울립니다

30분 탐색
반복되는 확인
프로덕션 접근 불안
```

- 좌측 문제 키워드와 우측 실제 알람 캡처를 40:60으로 나눈다.
- 긴 불릿은 지우고 내용은 대본에서 설명한다.

---

## [수정] Slide 3/15 — 해결 구조

현재 3개 역할은 아래 흐름 하나로 묶는다.

```text
Slack 요청  →  AI 진단  →  사람 승인
```

- `Slack Assistant DM`, `Claude 분석`, `사람 승인` 카드 3개만 크게 보여준다.
- `/devops logs`, `/devops diagnose`, `/devops tf-review`, `/devops pr`는 하단의 작은 배지로 정리한다.
- 대상 사용자와 MVP 범위는 화면에서 빼고 대본에 둔다.
- `simple.png`는 우측 보조 이미지로만 검토한다. 카드 흐름과 겹치면 넣지 않는다.

---

## [수정] Slide 4/15 — Safe-Autonomy Loop

현재 7단계 흐름은 5단계만 남긴다.

```text
DETECT  →  PROPOSE  →  NOTIFY  →  APPROVE  →  EXECUTE & VERIFY
```

- 사람 승인은 오렌지, 실행과 검증은 초록색으로 구분한다.
- 하단 설명 4개는 삭제한다.
- 흐름도를 화면 중앙에 키우고 아래 문장 하나로 닫는다.

```text
조사는 자동, 변경은 승인 후
```

---

## [수정] Slide 5/15 — 현재 아키텍처

좌측 카드와 작은 아키텍처 이미지를 나란히 놓은 현재 구성은 버린다.

- `docs/presentation/Architecture.png`를 화면 중앙에 크게 쓴다.
- 다이어그램을 다시 설명하는 문장은 넣지 않는다.
- 상단이나 좌측에는 아래 3개 키워드만 둔다.

```text
MULTIPLE INPUTS
SINGLE-TABLE QUEUE
HUMAN-BOUND WRITE
```

- 아키텍처 이미지의 불필요한 여백을 잘라 작은 화면에서도 읽히게 한다.
- 세부 흐름과 역할 분리는 `PRESENTATION.md` Slide 5에서 말한다.

---

## [수정] Slide 6/15 — 런타임 보안 경계

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

- 하단 standards rail에는 `OWASP LLM01 · LLM02 · LLM06 · ASI03`만 적는다.
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

## [수정] Slide 14/15 — OWASP 위험을 런타임 통제로 바꿨습니다

설계 교훈 카드 5개를 없애고 `위험 → 구현 → 증명` 한 장으로 바꾼다. 표처럼 빽빽하게 그리지 말고, 왼쪽에서 오른쪽으로 읽히는 가로 연결선 5개를 사용한다.

```text
위험                         구현                              증명
LLM01 Prompt Injection       <untrusted_data> · L0 tools=0    인젝션 명령 거부
LLM02 Data Disclosure        fixed adapter · egress allowlist 미허용 통신 차단
LLM05 Output Handling        diff review · plan hash          변경된 계획 거부
LLM06 Excessive Agency       command_guard · L2 off           restart/apply 거부
ASI03 Identity Abuse         role split · JIT write token     발급·회수 감사 기록
```

- 위험 열은 연한 주황, 구현 열은 AWS 블루, 증명 열은 초록으로 구분한다.
- 각 행은 아이콘 1개, 키워드 2개 이하, 증명 문구 1개만 둔다.
- 영어 OWASP 항목명은 작게, 한국어 증명 문구는 가장 크게 보이게 한다.
- 별도 설명 문단과 장식용 카드는 넣지 않는다.
- 하단에는 `OWASP LLM Top 10 2025 · Agentic Security Initiative Top 10`만 작게 적는다.
- 세부 구현과 검증 범위는 `PRESENTATION.md` Slide 14 대본에서 설명한다.

---

## [수정] Slide 15/15 — 클로징

다크 네이비 배경은 살리고 해커톤 푸터는 지운다.

```text
AI는 조사하고 제안합니다
사람은 diff를 검토하고 경계를 지킵니다

github.com/men16922/slackops-devops-agent
AWSKRUG DevOps 소모임
```

- 우측 세로 인포그래픽은 `docs/presentation/simple.png`로 바꾼다.
- 인포그래픽이 본문을 압도하면 크기를 줄이고 여백을 넓힌다.
- `지금 바로 시작해 보세요!` 문장은 삭제한다.

---

## 발표자 대본으로 옮길 내용

아래 내용은 슬라이드에 쓰지 않는다. `PRESENTATION.md` 대본에서 설명한다.

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
- **OWASP:** genai.owasp.org — LLM Top 10 2025 · OWASP Top 10 for Agentic Applications 2026.
- **AWS:** aws.amazon.com/blogs/security — 모델 밖 최소 권한 인가와 high-consequence 행동의 사람 승인.

## 최종 검수 기준

- 15장 번호와 순서가 `SlackOps DevOps Agent V2.pptx`와 맞는다.
- 슬라이드마다 핵심 메시지가 하나만 남는다.
- 발표자가 말할 설명 문단은 화면에 남지 않는다.
- 프로젝터에서도 핵심 키워드와 캡처가 읽힌다.
- `Architecture.png`, `simple.png`, 실제 Slack·대시보드 캡처가 선명하다.
- 모든 수치와 검증 상태가 `PRESENTATION.md`와 같다.
