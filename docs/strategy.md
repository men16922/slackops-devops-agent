# SlackOps 보안·제품 전략 — 쉬운 시작에서 전문가 증거까지

기준일: 2026-07-15
대상: `slackops-devops-agent`

## 1. 전략 한 줄

SlackOps의 전략은 **AI에게 운영 권한을 넓게 주는 것**이 아니라, 운영자가 자연어로
빨리 이해하고 안전하게 다음 행동을 결정하도록 돕는 것이다.

```text
입문자: 무엇이 문제인지 빠르게 이해
운영자: 근거를 보고 안전한 다음 행동을 제안
전문가: 권한·도구·네트워크·승인·감사의 증거를 검토
```

세 단계의 보안 경계는 같다. 사용자에게 보이는 설명과 선택 가능한 깊이만 다르다.

## 2. 2026 agent 보안 트렌드와 제품 원칙

2025년 12월 OWASP Agentic Top 10은 Agent Goal Hijack, Tool Misuse, Identity & Privilege
Abuse, Agentic Supply Chain, Unexpected Code Execution을 핵심 위험으로 제시했다.
[OWASP](https://genai.owasp.org/2025/12/09/owasp-top-10-for-agentic-applications-the-benchmark-for-agentic-security-in-the-age-of-autonomous-ai/)
2026년의 차별점은 모델 필터 하나가 아니라, **외부 데이터가 모델 판단을 흔들어도 실제
권한·도구·네트워크·승인 경계가 피해를 제한하는가**다.

OpenAI도 prompt injection이 단순 문자열 우회보다 사회공학적 맥락 조작으로 진화하고 있어,
입력 분류만으로 해결할 수 없다고 설명한다. 따라서 source(외부 데이터)와 sink(위험한
도구·전송)를 함께 줄여야 한다. [OpenAI](https://openai.com/index/designing-agents-to-resist-prompt-injection/)
AWS 역시 모델 외부의 최소 권한 인가와 high-consequence 행동의 사람 승인을 권장한다.
[AWS AI Security Framework](https://aws.amazon.com/blogs/security/the-aws-ai-security-framework-securing-ai-with-the-right-controls-at-the-right-layers-at-the-right-phases/)

SlackOps는 이 흐름을 다음 다섯 원칙으로 번역한다.

| 원칙 | 제품 결정 |
| --- | --- |
| 모델은 정책 엔진이 아니다 | 권한·금지 행동·승인 조건은 결정적 코드와 IAM이 집행한다. |
| 외부 데이터는 명령이 아니다 | Slack·로그·Git·MCP 응답을 `<untrusted_data>`로 격리한다. |
| 가장 좁은 도구가 기본값이다 | 범용 AWS MCP 대신 목적별 fixed read adapter를 쓴다. |
| 승인은 의도가 아니라 상태에 묶인다 | plan hash·도구 체인·workspace·PR diff를 실행 직전에 재검증한다. |
| 보안은 증명 가능해야 한다 | audit/telemetry, CI lock, 공격 corpus, 배포 검증으로 근거를 남긴다. |

## 3. 현재 리포의 구현 현황

아래 상태는 반드시 구분해서 말한다. `실환경 적용`과 `코드 준비 완료`를 섞으면 보안
신뢰가 떨어진다.

| 영역 | 구현 내용 | 상태와 근거 |
| --- | --- | --- |
| 권한·승인 | L0/L1만 활성, production/deploy/IAM/DB hard deny, Slack 승인자 allowlist, GitHub OAuth, immutable execution plan/hash, workspace·도구·원격 PR diff 재검증 | **실환경 적용 확인:** D15 dashboard/OAuth. 코드와 기존 실증은 `docs/STATUS.md`. |
| 결정적 scope | root-owned account/region/log-prefix/workspace와 명령별 고정 time window를 adapter·executor·Claude 직전에 확인 | **실 EC2 검증:** unreviewed log group은 fetch 전에 거부되고 Worker가 `policy_denied` reason/context를 기록. |
| 입력 격리 | prompt template 강제, forged untrusted tag neutralization, Slack/log/Git/kubectl/adapter error 단일 untrusted boundary | **구현·CI 확인:** sanitizer와 command tests. |
| AWS 읽기 경계 | `logs`·`diagnose`·`detect`가 범용 AWS API MCP 없이 command-specific boto3 read adapter로 evidence만 수집; L0 모델 tool allowlist는 비어 있음 | **실 EC2 검증:** runtime role의 fixed AWS read 성공. |
| credential 격리 | bootstrap Instance Profile → runtime role/MCP role, 1시간 STS credential·45분 회전, Claude env에서 AWS/DDB credential 제거, IMDS 차단 | **실 EC2 검증:** role identities·forced refresh·timer·4 services. |
| egress 경계 | 4개 agent 서비스는 non-loopback IP를 거부하고 localhost Squid allowlist를 통해 Slack·Claude·GitHub·AWS·Terraform 도메인만 통신 | **실 EC2 검증:** GitHub allow, unlisted domain·IMDS deny. |
| MCP 공급망 | 내부 `slackops` MCP의 source SHA-256, stdio command, tools, credential scope, owner, review date를 registry로 고정 | **CI 확인:** 드리프트 시 테스트 실패. |
| 감사 궤적 | 앱 hash-chain audit에 더해, 배포 운영자가 만든 30일 CloudWatch sink에 root-only audit role이 credential rotation과 URL-free Squid deny를 기록 | **실 EC2 검증:** audit env `600`, state `700`, agent unreadable; runtime sink write explicit deny; `credential_refresh`·`proxy_denied` 확인. |
| 지속 검증 | 인젝션 5종과 승인 후 path traversal·untracked 파일 corpus가 로그/진단/탐지/Terraform·execution plan에서 fail-closed인지 검증 | **CI 확인:** versioned corpus. |

현재 로컬 `main`은 hash-verified archive로 fresh EC2 rehearsal을 통과했지만, 원격 `main`
반영과 지속 운영 배포는 별개다. 이 차이는 발표·영업·보안 심사에서 명시한다.

## 4. 입문자에게 주는 임팩트: 복잡성을 숨기고 결과를 먼저

### 입문자가 보는 경험

입문자는 IAM, MCP, STS를 배우지 않아도 된다. 첫 화면과 첫 문서의 언어는 아래 세 문장으로
끝낸다.

1. **확인:** “checkout 서비스가 왜 느려?”라고 물으면 근거와 요약을 받는다.
2. **제안:** 변경이 필요하면 시스템이 실행하지 않고 계획과 위험을 보여 준다.
3. **승인:** 사람이 확인한 동일 계획만 다음 단계로 갈 수 있다.

첫 경험은 자격증명 없이도 가능해야 한다.

```sh
make install
make demo-assistant-mock
```

그 다음에만 Slack 명령과 실제 AWS 연결을 소개한다.

```text
/devops logs checkout-service
/devops diagnose checkout-service
/devops detect config
```

### 입문자용 성공 지표

| 목표 | 측정 방법 |
| --- | --- |
| 첫 가치 도달 | mock demo에서 “질문 → 요약 → 제안”을 10분 안에 이해하는가 |
| 안전한 기대 형성 | 사용자가 “직접 변경하지 않는다”를 설명할 수 있는가 |
| 다음 행동 명확성 | 결과에 근거·불확실성·권장 다음 행동이 함께 있는가 |

## 5. 실무 운영자에게 주는 임팩트: 빠르되 통제된 대응

운영자의 문제는 “AI가 답을 잘하나”보다 **장애 중에 무엇을 먼저 보고, 누가 언제 판단하나**다.
SlackOps는 아래 흐름을 제품의 기본 단위로 만든다.

```text
자연어 질문 또는 이벤트 신호
        ↓
고정 범위 읽기와 evidence 요약
        ↓
진단 또는 검토 작업 제안
        ↓
diff·영향·계획을 사람에게 표시
        ↓
승인된 동일 상태만 실행·감사
```

운영자에게 보여 줄 정보는 보안 구현 세부가 아니라 다음 다섯 가지다.

- 무엇이 관측됐는가
- 근거는 어디에서 왔는가
- 지금은 읽기인가, 제안인가, 승인 대기인가
- 사람이 결정해야 하는 영향은 무엇인가
- 나중에 누가 어떤 계획을 승인했는가

이 구조는 “모든 행동을 승인하는 bot”보다 승인 피로를 줄인다. 읽기·진단은 빠르게,
변경은 좁은 승인으로 분리하기 때문이다.

## 6. 플랫폼·보안 전문가에게 주는 임팩트: 설계가 아니라 증거

전문가는 “안전하다”는 말보다 다음 질문의 증거를 원한다.

| 전문가 질문 | SlackOps의 증거 경로 |
| --- | --- |
| 로그 속 지시가 모델을 속이면? | sanitizer + tool-less L0 + fixed read adapter + injection corpus |
| 모델이 임의 AWS API를 호출하면? | generic AWS MCP 제거, command-specific read adapter, IAM role split |
| 모델/요청이 범위를 넓히면? | account·region·resource·time-window 고정 scope; root-owned config 외 범위는 adapter 전 거부 |
| credential이 subprocess/MCP로 새면? | env allowlist, IMDS deny, root-only short-lived credential file, MCP queue-only credential |
| 공급망이 도구를 바꾸면? | MCP registry hash/command/tool inventory CI lock |
| 승인 후 diff가 바뀌면? | execution plan hash, workspace·tool-chain·remote PR diff recheck, `plan_binding_rejected` audit event |
| agent가 외부로 데이터를 보내면? | direct egress deny + localhost domain allowlist proxy (GitHub allow·unlisted deny 실증) |
| 경계 이벤트를 agent가 지우거나 꾸미면? | 별도 root-only audit role + agent-unwritable CloudWatch sink; runtime write explicit deny, refresh/deny event 실증 |

AWS managed MCP가 IAM context key와 감사·네트워크 통제를 제공하는 방향으로 발전하는 것은
긍정적이지만, 이 리포의 기본 경로를 범용 MCP로 되돌릴 근거는 아니다. AWS MCP Server는
많은 AWS API를 다룰 수 있으므로, 향후 도입은 별도 전문가 환경에서 identity context,
resource/action allowlist, write approval, CloudTrail evidence를 갖춘 경우에만 검토한다.
P3는 이 원칙을 `deploy/mcp/managed-aws-pilot/`에 별도 계정 계약, 세 개의 Logs read action,
AWS-managed-MCP context key, CloudTrail 위반 조회로 고정했다. 이는 scaffold일 뿐 AWS 역할·endpoint·세션을
배포한 상태는 아니다. VPC endpoint는 선택한 서버와 Region에서 지원되는지 운영자가 확인한 뒤에만 요구한다.
[AWS MCP IAM guidance](https://aws.amazon.com/blogs/security/understanding-iam-for-managed-aws-mcp-servers/)

## 7. 발표·도입 전략

### 7.1 발표의 순서

1. **사용자 문제:** “장애 때 로그는 많은데, 무엇을 믿고 다음 행동을 정할까?”
2. **쉬운 흐름:** 자연어 질문 → evidence 요약 → 사람에게 제안.
3. **멈추는 장면:** 로그 속 악성 지시, 직접 변경, 변경된 diff가 각각 거부된다.
4. **전문가 증거:** fixed adapter, role split, egress, approval hash, registry/corpus.
5. **전문가 증거:** D17/P1/P2 fresh-EC2 rehearsal에서 runtime write deny, 중앙 audit, pre-fetch scope deny를 보여 준다.

### 7.2 도입 단계

| 단계 | 대상 | 제공 가치 | 도입 조건 |
| --- | --- | --- | --- |
| 0. 학습 | 개인·입문자 | mock으로 안전한 흐름 이해 | AWS/Slack credential 불필요 |
| 1. 관찰 | 서비스 운영자 | logs/diagnose/detect의 read-only triage | 서비스·로그 범위 등록 |
| 2. 제안 | 팀 리드 | Terraform/PR 검토·승인 queue | 승인자와 GitHub OAuth 설정 |
| 3. 통제 | 플랫폼·보안팀 | roles, egress, audit, corpus, MCP registry | fresh EC2 rehearsal·운영 runbook |
| 4. 확장 | 규제·다계정 조직 | managed MCP/VPC endpoint/SCP·central audit 검토 | 계정 경계·identity context·compliance 요구 확정 |

### 7.3 발표에서 피할 표현

- “prompt injection을 해결했다” → **모델이 속아도 sink를 줄이는 경계를 구현했다**
- “AWS를 자연어로 조작한다” → **정해진 범위에서 읽고, 변경은 증거와 승인을 거친다**
- “D17이 production에 상시 배포됐다” → **fresh EC2 rehearsal 완료, remote-main 지속 배포는 별도**

## 8. 다음 30일 우선순위

1. **P3 — 조직 확장:** managed AWS MCP가 필요한 특정 업무만 별도 role·context key·VPC
   endpoint·CloudTrail governance로 pilot한다.

## 9. 성공 기준

| 관점 | 30일 확인 질문 |
| --- | --- |
| 입문자 | mock demo만으로 읽기·제안·승인의 차이를 이해하는가 |
| 운영자 | 실제 장애 질문에서 근거와 다음 행동을 더 빨리 결정하는가 |
| 보안팀 | 공격 corpus·MCP registry·approval recheck·IAM/egress 증거를 재실행할 수 있는가 |
| 경영·발표 | “AI가 더 많은 권한을 가진다”가 아니라 “AI의 영향 범위를 증명 가능하게 줄였다”는 메시지가 전달되는가 |

## 참고 자료

- [OWASP Top 10 for Agentic Applications](https://genai.owasp.org/2025/12/09/owasp-top-10-for-agentic-applications-the-benchmark-for-agentic-security-in-the-age-of-autonomous-ai/)
- [OpenAI: Designing agents to resist prompt injection](https://openai.com/index/designing-agents-to-resist-prompt-injection/)
- [AWS: Four security principles for agentic AI](https://aws.amazon.com/blogs/security/four-security-principles-for-agentic-ai-systems/)
- [AWS: IAM for managed MCP servers](https://aws.amazon.com/blogs/security/understanding-iam-for-managed-aws-mcp-servers/)
- [AWS: Agentic AI security scoping matrix](https://aws.amazon.com/blogs/security/the-agentic-ai-security-scoping-matrix-a-framework-for-securing-autonomous-ai-systems/)
