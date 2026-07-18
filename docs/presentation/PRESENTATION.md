# SlackOps DevOps Agent - AWSKRUG 발표 대본

> 기준 발표본: `docs/presentation/SlackOps.pdf` (18장)
> 발표: AWSKRUG DevOps 소모임, 2026-07-23
> 발표자: 최병민, 현대오토에버
> 청중: AWS 실무자, DevOps/SRE, 보안 엔지니어
> 구성: 발표 20분 + Q&A 10분
> 라이브 시연: [LIVE.md](LIVE.md)

## 발표의 한 문장

AI 에이전트의 보안은 모델이 절대 속지 않게 만드는 일이 아니라, 속더라도 실제 행동과 권한이 통제되도록 시스템 경계를 설계하는 일이다.

## 시간 배분

| 구간 | 슬라이드 | 목표 시간 |
| --- | --- | ---: |
| 문제 정의 | 1-4 | 4분 |
| SlackOps 구조 | 5-8 | 5분 |
| 통제와 증거 | 9-15 | 5분 30초 |
| 라이브 시연 | 16 | 4분 30초 |
| 정리 | 17-18 | 1분 |

라이브가 4분 30초를 넘으면 진단 결과 설명을 줄이고, PR 생성 결과만 확인한 뒤 Slide 17로 돌아간다.

## 발표 원칙

- 화면의 작은 글자를 읽지 않는다. 각 슬라이드에서 굵게 보이는 메시지와 증거만 말한다.
- 모델의 안전성을 주장하지 않는다. 권한, 승인, 실행기, 네트워크가 피해 범위를 줄인다고 설명한다.
- "모든 공격을 막았다"고 말하지 않는다. 실제로 구현하고 검증한 범위만 말한다.
- `Managed MCP`는 현재 런타임에 연결하지 않았으며 라이브 증명 범위가 아니다.
- `L0 tools=0`은 모델의 분석 단계에 범용 실행 도구를 주지 않았다는 뜻으로 설명한다.

---

# 1. 문제 정의

## Slide 1/18 - SlackOps DevOps Agent

### 화면 메시지

```text
SlackOps DevOps Agent
보안팀도 승인할 수 있는 AI 운영 에이전트

Read-only by default
Human approval gate
```

### 발표 대본

"안녕하세요. 현대오토에버 최병민입니다. 오늘은 AI가 장애를 얼마나 잘 진단하는지보다, AI 운영 에이전트의 행동을 어떻게 통제할 수 있는지 이야기하겠습니다."

"제가 만든 SlackOps DevOps Agent를 사례로, 읽기는 기본적으로 제한하고 변경은 사람이 승인하는 구조를 실제 구현과 거부 결과, 그리고 라이브 시연으로 보여드리겠습니다."

### 전환

"먼저 챗봇과 에이전트의 실패가 왜 다른지부터 보겠습니다."

---

## Slide 2/18 - AI 에이전트의 오답은 실제 행동이 됩니다

### 화면 메시지

```text
AI Agent = 판단 + 도구 + 권한

챗봇의 오답 -> 잘못된 정보
에이전트의 오답 -> 실제 행동
```

### 발표 대본

"챗봇은 프롬프트를 받아 답변을 돌려줍니다. 반면 에이전트는 목표를 해석하고, 이유를 판단하고, 도구를 호출해 시스템에 영향을 줍니다. 모델의 출력이 실제 시스템의 입력이 된 것입니다."

"그래서 챗봇의 오답은 대체로 잘못된 정보로 끝나지만, 에이전트의 오답은 메시지 전송, 코드 변경, 인프라 조작 같은 행동이 될 수 있습니다."

"중요한 질문은 '에이전트가 틀리는가'가 아닙니다. 에이전트가 틀리거나 속았을 때 어디까지 행동할 수 있는가입니다."

### 발표 포인트

- 오른쪽 그림은 `Goal -> Reason -> Tool -> System`에서 실제 권한이 연결되는 지점만 짚는다.
- OpenAI의 핵심 취지는 악성 입력을 완벽히 식별하는 것뿐 아니라, 조작에 성공해도 영향이 제한되도록 설계하는 것이다.

---

## Slide 3/18 - AI 에이전트 보안은 필수 조건입니다

### 화면 메시지

```text
GOAL & CONTEXT
TOOLS & IDENTITY
ECOSYSTEM & OPERATIONS

OWASP Top 10 for Agentic Applications 2026
```

### 발표 대본

"이 변화 때문에 보안의 범위도 프롬프트 인젝션 하나에서 에이전트 전체 구조로 넓어졌습니다."

"첫 번째는 목표와 컨텍스트입니다. 비신뢰 입력이 목표를 바꾸거나 메모리를 오염시킬 수 있습니다. 두 번째는 도구와 권한입니다. 허용된 도구도 잘못 조합할 수 있고, 에이전트의 계정이나 토큰을 악용할 수 있습니다. 세 번째는 생태계와 운영입니다. 공급망, 에이전트 간 통신, 연쇄 실패, 사람의 과신까지 포함됩니다."

"따라서 강한 시스템 프롬프트나 입력 필터 하나만으로는 충분하지 않습니다. 모델이 실패한 뒤에도 남아 있는 실행 권한과 통신 경로를 함께 줄여야 합니다."

### 전환

"이제 이 위험을 PoC에서 프로덕션으로 옮길 때 어떤 질문으로 바꿔야 하는지 보겠습니다."

---

## Slide 4/18 - PoC의 성공은 운영 안전을 보장하지 않습니다

### 화면 메시지

```text
PoC
작업을 수행할 수 있는가?

프로덕션
무엇을 읽는가?
무엇을 실행하는가?
누구의 권한을 쓰는가?
멈추고 감사할 수 있는가?
```

### 발표 대본

"PoC에서는 자연어 요청을 받아 작업을 끝내는지가 중요합니다. 프로덕션에서는 질문이 달라집니다. 무엇을 읽을 수 있는지, 무엇을 실행할 수 있는지, 누구의 권한을 사용하는지, 문제가 생기기 전에 멈추고 사후에 감사할 수 있는지를 답해야 합니다."

"한 번 성공한 데모는 안전성을 증명하지 않습니다. 같은 통제가 반복해서 적용되고, 승인한 내용과 실제 실행이 같고, 실패와 거부까지 추적돼야 합니다."

"그래서 프로젝트의 질문을 이렇게 정했습니다. 속아도 안전한 운영 에이전트를 만들 수 있을까?"

---

# 2. SlackOps 구조

## Slide 5/18 - 새벽 2시 온콜을 하나의 구현 사례로 잡았습니다

### 화면 메시지

```text
새벽 2시, 알림이 울립니다

콘솔을 오가며 로그 확인
수동 원인 분석
반복되는 온콜 대응

AI가 대신할 수 있을까?
```

### 발표 대본

"구현 사례는 반복되는 온콜 대응입니다. 새벽에 알림이 오면 여러 콘솔을 오가며 로그와 배포 이력, 지표를 확인하고 원인을 좁힙니다. 조사 자체는 AI가 잘 도울 수 있는 영역입니다."

"하지만 운영 환경에서는 바로 다음 세 가지가 문제입니다. AI가 프로덕션을 변경할 수 있다는 것, 자격 증명이 노출될 수 있다는 것, 그리고 로그나 티켓 안의 악성 지시가 모델을 속일 수 있다는 것입니다."

"SlackOps는 AI가 조사와 제안을 담당하되, 변경 권한은 분리하는 방식으로 이 문제를 풀었습니다."

---

## Slide 6/18 - Slack 요청, AI 진단, 사람 승인

### 화면 메시지

```text
Slack 요청 -> AI 진단 -> 사람 승인

/devops logs
/devops diagnose
/devops tf-review
/devops pr
```

### 발표 대본

"사용자는 Slack Assistant DM이나 명령으로 요청합니다. 에이전트는 정해진 읽기 경로에서 증거를 모아 진단하고, 변경이 필요하면 diff를 먼저 제안합니다. 사람은 승인 카드에서 변경 내용을 확인하고 실행 여부를 결정합니다."

"여기서 핵심은 자연어 인터페이스가 실행 권한을 직접 갖지 않는다는 점입니다. 자연어는 요청을 만들고, 실제 실행 여부는 별도의 상태와 정책 경계가 결정합니다."

### 전환

"이 흐름을 상태 관점에서 보면 다섯 단계입니다."

---

## Slide 7/18 - 탐지와 진단은 자동, 변경은 승인 후 실행

### 화면 메시지

```text
DETECT -> PROPOSE -> NOTIFY -> APPROVE -> EXECUTE & VERIFY
```

### 발표 대본

"SlackOps의 안전 자율 루프는 Detect, Propose, Notify, Approve, Execute and Verify 다섯 단계입니다."

"탐지와 진단, 제안까지는 자동화합니다. 그러나 변경은 승인 상태가 확인된 뒤에만 실행합니다. 실행이 끝나도 성공으로 바로 끝내지 않고, 승인한 계획과 실제 결과가 일치하는지 다시 검증합니다."

"즉 자율성은 조사와 제안에 주고, 변경 권한은 사람과 결정적 실행기에 묶었습니다."

---

## Slide 8/18 - 현재 아키텍처

### 화면 메시지

```text
MULTIPLE INPUTS
SINGLE-TABLE QUEUE
HUMAN-BOUND WRITE
```

### 발표 대본

"이 그림을 전부 읽지는 않겠습니다. 세 줄만 보시면 됩니다."

"첫째, 왼쪽과 위쪽의 여러 입력입니다. Slack, 웹 대시보드, CloudWatch 이벤트가 작업을 만듭니다. 둘째, 가운데 DynamoDB 단일 테이블입니다. Job Queue와 승인 상태, 감사와 텔레메트리가 한 작업 ID를 따라갑니다. 셋째, 아래쪽의 분리된 두 경로입니다. 왼쪽은 고정된 읽기 어댑터를 통한 분석 경로이고, 오른쪽은 승인된 계획만 PR로 만드는 쓰기 경로입니다."

"오른쪽 Safety Invariants는 이 구조가 지켜야 하는 불변 조건입니다. 역할 분리, 고정 어댑터, egress allowlist, plan binding, 단기 토큰, capability drift gate가 모델 밖에서 강제됩니다."

### 레이저 포인터 순서

1. Slack/CloudWatch 입력
2. DynamoDB single-table queue
3. Read/Analysis Path
4. Approved Write Path
5. Safety Invariants

---

# 3. 통제와 증거

## Slide 9/18 - 상시 권한과 임의 통신을 두지 않습니다

### 화면 메시지

```text
IDENTITY SPLIT
SHORT-LIVED STS
EGRESS ALLOWLIST

상시 권한은 두지 않는다
```

### 발표 대본

"첫 번째 런타임 경계는 역할 분리입니다. 부팅 역할과 runtime, internal MCP, audit 역할을 나눴습니다."

"두 번째는 단기 자격 증명입니다. STS 자격은 1시간 뒤 만료되고 45분마다 교체합니다. AI 자식 프로세스는 IMDS에 직접 접근하지 못합니다."

"세 번째는 외부 통신입니다. 모든 트래픽은 Squid allowlist를 거치고 Slack, Claude, GitHub, AWS, Terraform처럼 필요한 목적지만 허용합니다. 모델이 데이터 유출 지시를 따르더라도 임의 목적지로 보낼 통로를 주지 않는 설계입니다."

---

## Slide 10/18 - 요청에서 제안까지는 읽기 전용입니다

### 화면 메시지

```text
FIXED READ ADAPTER
L0 TOOLS = 0
$0.15 / RUN

Slack 요청 -> CloudWatch 증거 -> 진단 -> PR 제안
```

### 발표 대본

"Slack 요청이 들어오면 command별 fixed read adapter가 정해진 범위의 증거만 가져옵니다. 계정, 리전, 시간 범위와 로그 prefix는 코드와 런타임 정책에 고정돼 있습니다."

"외부 데이터는 `<untrusted_data>` 경계에 넣고 Claude에는 분석만 맡깁니다. 이 L0 단계의 범용 도구 allowlist는 0입니다. 모델이 보는 로그 안에 명령이 있어도 실행할 Bash나 AWS 도구가 없습니다."

"진단 결과에는 근거와 다음 행동, 비용이 함께 남습니다. 변경이 필요하면 PR을 제안하지만 아직 쓰기 권한은 발급되지 않습니다."

### 발표 포인트

- 오른쪽 Slack 캡처의 문장을 읽지 말고 `근거`, `제안`, `awaiting approval`만 짚는다.
- `$0.15 / RUN`은 슬라이드의 대표 실행 예시이며 고정 요금이라고 표현하지 않는다.

---

## Slide 11/18 - 승인한 내용 그대로만 실행합니다

### 화면 메시지

```text
PROPOSE -> REVIEW -> APPROVE -> EXECUTE

Plan-Then-Execute
TOCTOU defense
```

### 발표 대본

"변경 요청은 먼저 diff와 실행 계획을 만듭니다. Slack 버튼이나 Review change Modal에서 사람이 변경 내용을 확인하고 승인합니다."

"승인은 포괄적인 허가가 아닙니다. 승인 시점의 plan hash, 도구 체인, workspace, PR diff를 묶어 저장합니다. 실행 직전에 같은 값을 다시 계산해 한 글자라도 달라지면 멈춥니다."

"검증을 통과한 뒤에만 대상 저장소에 제한된 GitHub App 토큰을 발급합니다. LLM은 실행 단계에서 빠지고, 결정적 실행기가 branch와 PR을 만듭니다. 작업이 끝나면 토큰을 회수합니다."

### 화면 포인트

- 왼쪽 네 단계 중 `APPROVE`를 짚는다.
- 오른쪽 캡처에서는 PR 생성과 branch protection 문구만 짚는다.

---

## Slide 12/18 - 모든 입구가 하나의 작업 큐를 공유합니다

### 화면 메시지

```text
SINGLE TABLE
CONDITIONAL CLAIM
AUDIT + TELEMETRY

Slack · Vercel · Agent · Event-driven Lambda
```

### 발표 대본

"Slack, Vercel, resident agent, Event-driven Lambda가 만든 작업은 모두 같은 DynamoDB 테이블로 들어갑니다. 입구는 여러 개지만 상태 전이 규칙은 하나입니다."

"worker는 DynamoDB conditional write로 작업을 선점합니다. 두 worker가 동시에 접근해도 한쪽만 성공하므로 중복 실행을 막습니다. 승인, 실행, 실패, 비용, 토큰, 감사 이벤트도 같은 job ID를 따라 기록됩니다."

"DynamoDB를 선택한 이유는 단순한 데이터 저장이 아니라, 별도 coordinator 없이 atomic claim과 optimistic-lock 승인 게이트를 만들기 위해서입니다."

---

## Slide 13/18 - 세 가지 위험 요소를 한 에이전트에 결합하지 않습니다

### 화면 메시지

```text
PRIVATE DATA
UNTRUSTED CONTENT
EXTERNAL COMMUNICATION

L0 TOOLS = 0
SHORT-LIVED STS
NO STANDING WRITE CREDENTIAL
```

### 발표 대본

"Simon Willison은 private data, untrusted content, external communication이 한 에이전트에 동시에 모이면 데이터 탈취로 이어질 수 있다고 설명합니다. Lethal Trifecta입니다."

"SlackOps는 세 요소를 모두 좁힙니다. private data는 fixed read adapter가 허용한 증거만 읽습니다. untrusted content는 격리된 데이터로 취급합니다. external communication은 Squid allowlist로 제한합니다."

"여기에 L0 tools=0, short-lived STS, no standing write credential을 더했습니다. 앞의 한 방어가 실패해도 다음 경계가 남도록 만든 것입니다."

---

## Slide 14/18 - 실행 비용과 결과를 함께 기록합니다

### 화면 메시지

```text
RUNS 107
TOKENS 92,070
COST $4.76
```

### 발표 대본

"통제는 보이는 형태로 남아야 운영할 수 있습니다. 이 화면은 실제 테스트와 검증 실행에서 쌓인 텔레메트리입니다. 107회 실행, 92,070 토큰, 총 비용 약 4.76달러를 command별로 추적했습니다."

"Detections에서는 IAM Access Analyzer, AWS Config, CloudWatch Alarm, SSM compliance 같은 탐지 항목을 명시적으로 켜고 끌 수 있습니다. Telemetry에서는 command별 성공, 지연 시간, 비용, 토큰, 도구 호출을 확인합니다."

"성공한 실행만 보여주는 것이 아니라 실패와 거부도 같은 피드에 남긴다는 점이 중요합니다."

### 주의

- 숫자는 이 화면을 캡처한 시점의 누적 테스트 값이다. 월 운영비나 일반적인 비용으로 확대 해석하지 않는다.

---

## Slide 15/18 - 거부 결과가 보안 경계의 증거입니다

### 화면 메시지

```text
READ-ONLY DENIED
PLAN BINDING REJECTED

승인 후 한 글자라도 바뀌면 실행하지 않는다
```

### 발표 대본

"왼쪽은 읽기 전용 경계를 넘는 동작이 거부된 결과입니다. restart, apply, delete 같은 동작은 모델의 답변이 아니라 command guard와 IAM 정책에서 막힙니다."

"오른쪽은 승인 뒤 계획이 바뀐 경우입니다. plan hash, tool chain, workspace, PR diff를 다시 비교하고 하나라도 다르면 `plan_binding_rejected`로 실행을 거부합니다."

"검증 범위도 분리해서 말씀드리겠습니다. EC2 경계는 실제 환경에서 확인했고, GitHub App 쓰기 경로는 실제 PR로 확인했습니다. Managed MCP는 현재 런타임에 연결하지 않았으며 이번 증명 범위가 아닙니다."

### 전환

"이제 이 흐름을 Slack에서 실제로 보여드리겠습니다."

---

# 4. 라이브와 결론

## Slide 16/18 - LIVE

### 화면 메시지

```text
Slack -> Diagnose -> Approve -> PR
```

### 무대 멘트

"지금부터 네 가지를 보겠습니다. 자연어 요청이 읽기 전용 진단으로 이어지는지, 변경 전에 diff에서 멈추는지, 승인한 계획만 실행되는지, 마지막으로 실제 PR이 생성되는지입니다."

이후 절차와 복구 분기는 [LIVE.md](LIVE.md)를 따른다.

### 복귀 멘트

"방금 보신 핵심은 AI가 PR을 만들었다는 기능이 아닙니다. 읽기 단계에는 쓰기 권한이 없었고, 변경 단계에는 사람이 승인한 diff와 실행 계획이 그대로 묶였다는 점입니다."

---

## Slide 17/18 - 위험을 구현과 증명까지 연결합니다

### 화면 메시지

```text
RISK -> IMPLEMENTATION -> PROOF
```

### 발표 대본

"처음에 본 OWASP 위험으로 돌아가겠습니다. SlackOps는 새로운 보안 이론을 만든 프로젝트가 아니라, 위험을 구현과 증거로 번역한 사례입니다."

"Goal Hijack에는 untrusted data 격리와 tools=0, Tool Misuse에는 fixed adapter와 command guard, Identity Abuse에는 역할 분리와 JIT write token을 적용했습니다. Unexpected Execution에는 결정적 실행기와 hash 재검증, Human-Agent Trust에는 diff review와 approver identity를 연결했습니다."

"중요한 것은 통제의 이름이 아니라 오른쪽 열입니다. 악성 목표가 실행되지 않았는지, 미허용 argv가 거부됐는지, 상시 write 권한이 0인지, 변경된 계획이 실제로 거부됐는지를 확인할 수 있어야 합니다."

---

## Slide 18/18 - 자율성은 에이전트에게, 통제권은 사람에게

### 화면 메시지

```text
AI는 조사하고 제안합니다.
사람은 Diff를 검토하고 결정합니다.

자율성은 에이전트에게,
통제권은 사람에게.
```

### 발표 대본

"오늘의 출발점은 AI 에이전트의 오답이 실제 행동이 된다는 문제였습니다. 그래서 프로덕션의 기준은 모델이 더 똑똑한가가 아니라, 틀리거나 속아도 읽기 범위, 실행 도구, 권한, 통신, 승인과 감사가 통제되는가입니다."

"SlackOps에서 AI는 조사하고 제안합니다. 사람은 diff를 검토하고 결정합니다. 실행 경계는 모델 밖의 코드와 IAM, 네트워크가 지킵니다."

"자율성은 에이전트에게, 통제권은 사람에게. 이것이 제가 AI 운영 에이전트를 프로덕션에 적용하기 위해 세운 기준입니다. 감사합니다."

---

# Q&A 핵심 답변

## 왜 사람 승인이 있으면 안전하다고 볼 수 있나?

사람의 판단 자체를 완벽하다고 가정하지 않는다. 승인 대상이 되는 diff와 plan hash, approver identity를 묶고, 실행 직전에 다시 검증한다. 사람 승인은 통제의 한 계층이고, command guard, IAM, 단기 토큰, branch protection이 추가 경계로 남는다.

## 프롬프트 인젝션을 해결한 것인가?

아니다. 비신뢰 입력이 모델의 판단을 왜곡할 가능성은 남아 있다. SlackOps의 목표는 입력을 완벽히 판별하는 것이 아니라, 모델이 속더라도 도구, 권한, 외부 통신과 쓰기 경로를 제한해 피해로 이어지는 sink를 줄이는 것이다.

## LLM이 실제 PR을 만드는가?

LLM은 prepare 단계에서 변경안과 diff를 제안한다. 승인 뒤 branch 생성, push, PR 생성은 LLM을 제거한 결정적 실행기 `app.pr_execution.open_pr`가 수행한다.

## 왜 DynamoDB single-table인가?

Slack, Vercel, agent, Lambda의 작업을 하나의 상태 머신으로 처리하고 conditional write로 atomic claim과 optimistic-lock 승인을 구현하기 위해서다. Job, audit, metric, timeline을 같은 ID로 조회할 수 있다.

## 상시 write 권한이 정말 없는가?

진단과 prepare 단계에는 write credential이 없다. 승인한 plan hash가 실행 직전에도 일치할 때만 대상 repository와 권한이 고정된 GitHub App installation token을 발급하고, 작업 종료 시 회수한다. branch protection은 에이전트가 만든 PR의 self-merge를 막는다.

## AWS Agentic AI Security Scoping Matrix에서 어디에 해당하나?

변경을 제안할 수 있지만 실행에는 사람의 명시적 승인이 필요한 구조이므로 Scope 2, Prescribed Agency에 가깝다. 읽기 전용 자동 진단 경로는 Scope 1 특성도 함께 가진다.

## Managed MCP를 사용하는가?

현재 운영 런타임에는 연결하지 않았다. 별도 계정과 제한된 role, context-key, CloudTrail 검증을 전제로 한 로컬/CI scaffold만 있다. 이번 발표의 라이브 증명에는 포함하지 않는다.

# 발표 전 최종 확인

- [ ] PDF 18장과 이 문서의 슬라이드 번호가 일치한다.
- [ ] Slide 4와 Slide 6의 페이지 번호가 프로젝터에서 정상 표시되는지 확인한다.
- [ ] Slide 8에서는 아키텍처 전체를 읽지 않고 다섯 포인터만 짚는다.
- [ ] Slide 10, 11, 14, 15의 캡처 화면은 작은 글자를 읽지 않는다.
- [ ] Slide 14 수치를 캡처 시점의 누적 테스트 값으로 설명한다.
- [ ] Slide 15에서 Managed MCP 미사용 범위를 명확히 말한다.
- [ ] Slide 16 진입 전에 Slack, 대시보드, GitHub 탭이 준비돼 있다.
- [ ] Slide 18 QR이 실제 휴대폰에서 최종 목적지까지 열린다.
- [ ] 라이브가 지연되면 `LIVE.md`의 A/B/C 복구 분기를 따른다.

# 출처

- OWASP GenAI Security Project, [OWASP Top 10 for Agentic Applications for 2026](https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/), 2025-12-09.
- OpenAI, [Designing AI agents to resist prompt injection](https://openai.com/index/designing-agents-to-resist-prompt-injection/), 2026-03-11.
- Simon Willison, [The lethal trifecta for AI agents](https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/), 2025-06-16.
- AWS, [The Agentic AI Security Scoping Matrix](https://aws.amazon.com/blogs/security/the-agentic-ai-security-scoping-matrix-a-framework-for-securing-autonomous-ai-systems/), 2025-11-21.
