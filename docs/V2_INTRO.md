# V2_INTRO — v1(H0 해커톤) → v2(AWSKRUG) 무엇이 강화됐나

> 대상: 발표 준비/이해관계자. 목적: 같은 프로젝트가 **해커톤 제출용(v1)**에서
> **AWSKRUG 실무 발표용(v2)**으로 바뀌며 서사·보안·아키텍처·데모가 어떻게 강화됐는지 한눈에.
> 근거: `docs/DECISIONS.md`(D6~D23) · `docs/presentation/PRESENTATION.md`(현행 대본) · git 이력
> (`123ed8e`/`78f0af8` = 초기 AWSKRUG deck, working tree = 현행). 상세 전략: `docs/strategy.md`·`docs/suggestion.md`.

## 0. 한 줄 요약

v1은 **"두 control plane이 하나의 DynamoDB 큐를 공유"**를 자랑하는 *대회 심사용 아티팩트*였고,
v2는 **"AI는 관찰·제안하고 실행은 사람만"**을 증명하는 *실무자 신뢰용 라이브 데모*다.
가장 크게 강화된 축은 **보안**이다 — 모델의 AWS 접근이 `MCP read-only`에서 **"범용 도구 아예 없음"**으로 좁혀졌다.

## 1. 축별 비교 (v1 → v2)

| 축 | v1 — H0 Slack 해커톤 | v2 — AWSKRUG 발표 | 강화 포인트 |
| --- | --- | --- | --- |
| 헤드라인 | "One Agent, Two Control Planes" (Slack+Vercel, DynamoDB 공유 큐) | "Slack 자연어로 AWS 진단, **사람이 경계를 지키는** AI 에이전트" | 대회 훅 → 실무 원칙 |
| 청중/목적 | Devpost 심사위원 (영상+설명+아키텍처 비중) | AWS 실무자(SRE/DevOps), 동료 신뢰 | 아티팩트 → 피어 크리덜리티 |
| 모델의 AWS 접근 | `AWS API MCP (read-only + strict)` | **fixed read adapter (범용 도구 미제공)** | ★ 최대 강화 (D13→D16) |
| 보안 위치 | 데모 한 스텝("write denied") | **전용 슬라이드(4층 보안) + 전용 인젝션 데모** | 부가 → 1급 축 |
| 데모 형식 | 녹화 <3분 연속 컷(영어 자막) | **라이브 20분**(녹화 없음), 데모 4개 | 심사 최적화 → 현장 시연 |
| Canvas 포스트모템 | 없음 | **자동 생성**(시연 2) | 신규 wow |
| 인스턴스/비용 | t3.medium / ~$12 (버전간 불일치) | **c7i.large / ~$22** (실 인프라 정합) | 정직한 수치 |
| DB 정당화 | *중심* 셀링포인트("DynamoDB 썼다") | 설계 교훈 1개로 강등 | 훅 → 근거 |
| 설계 교훈 슬라이드 | 없음 | **슬라이드 8 — 4개 명명된 교훈** | 제출물 → 재사용 지혜 |

## 2. 서사 프레이밍: 대회 → 실무

- **v1**은 Devpost 요건("Hack the Zero Stack", Track 2 B2B)에 맞춰 *"AWS Database used: DynamoDB"* 한 줄을
  중심에 놓고, "채점은 앱 테스트보다 영상+설명+아키텍처 비중이 크다"는 판단으로 **아티팩트 산출**에 최적화됐다.
- **v2**는 겪은 고통으로 연다 — *"새벽 3시, 혼자 온콜… AI에 프로덕션 접근 주면? '뭘 할지 모른다' = 공포"* —
  그리고 재사용 가능한 명제로 닫는다 — *"AI가 제안하고 벨을 울린다. 사람이 diff를 읽고 경계를 지킨다.
  그게 에이전트를 프로덕션에서 안전하게 돌리는 방법."* 제출물이 아니라 **전이 가능한 아키텍처 교훈**이 됐다.

## 3. 보안 강화 — 핵심 (모델의 AWS 접근)

가장 중요한 변화. v1 및 초기 v2 deck(`123ed8e`/`78f0af8`)은 데이터 소스를 `AWS API MCP (read-only)`로 그렸고
시연 대본도 *"AWS API MCP 서버를 통해 read-only로 접근합니다"*였다. **현행 deck은 이를 제거**하고
*"모델에는 범용 AWS 도구를 주지 않았습니다 — 앱의 fixed read adapter가 CloudWatch 증거만 가져옵니다"*로 바꿨다.

- 슬라이드 5 불변식도 재작성: 구 `IAM read-only + READ_OPERATIONS_ONLY + --strict-mcp-config`(도구 설정 플래그)
  → 신 `IAM least privilege + fixed API allowlist + single untrusted-data boundary`(**아키텍처 보장**).
- 근거: 범용 read MCP는 (읽기전용이어도) secret·무관 데이터·로컬 파일을 노출할 수 있고 tool_result가
  `<untrusted_data>` 경계를 우회했다 → D16에서 고정 adapter로 되돌림(정책을 결정적 코드로).

## 4. 그 밖의 보안 하드닝 (D15~D23, v2 기간에 쌓임)

발표에서 "4층 보안" 뒤를 받치는 실제 구현. 테마별 한 줄:

- **신원/인증** — 대시보드 모든 라우트에 GitHub OAuth + fail-closed `GITHUB_ALLOWED_USERS`; Slack은
  `SLACK_APPROVER_IDS` 버튼 allowlist. 빈 값 = 전부 거부. (D15)
- **최소권한 AWS** — bootstrap-only Instance Profile + 단기 runtime/MCP + root-only audit role 분리;
  account/region/prefix/workspace를 root-owned env로 고정해 매 호출 전 재검사. (D17/P1/P2)
- **프롬프트 인젝션** — 모든 비신뢰 입력(Slack/log/kubectl/git/adapter error)이 단일 `<untrusted_data>`
  경계로; L0 분석은 도구 없음. 남은 위험(격리 데이터 내부 의미 인젝션)은 tool-less 분석 + 권한/출력 게이트로 억제. (D16)
- **승인/출력 게이트** — L1 write는 diff 먼저 게시 후 정지; 승인 시 canonical `ExecutionPlan` 해시(요청/diff/
  경로/workspace/정책/도구체인)를 저장하고 실행 직전 재대조 → TOCTOU·path traversal·symlink·untracked·
  승인후 diff 변경을 실행 전 거부. execute 단계엔 Edit/Write/checkout 없음. (D15)
- **write credential** — PR execute는 상시 자격 0; 승인 plan hash 재검증 직후에만 저장소·권한 고정
  GitHub App installation token을 발급→한 자식 env 주입→종료 시 회수→job/approval hash로 감사(토큰 미로그).
  실행 경계는 PreToolUse `command_guard`(argv 스키마) — `--allowedTools`만으론 `echo hi; whoami`가 실행됨을 실측. (D19)
- **capability drift 게이트** — 도구마다 5-class capability 선언(미분류=fail closed), plan 위험은 도구체인
  distinct capability 합 vs `RISK_CEILING=10`; worker가 **실제로 실행된** capability를 재계산해 승인 초과 시
  `capability_drift`로 job 실패. "허용된 것"과 "실행된 것"이 독립 산술 체크 둘. (D20/D22/D23)
- **감사/관측** — 배포가 만든 root-only `/slackops/security-boundary-audit` sink(런타임 write 명시적 deny)에
  경계 증거; 앱 감사는 stream-json 관측으로 실제 tool_call을 담은 hash-chain step tree; OTel run-span 위에. (P1/D21/D22)

## 5. 검증 상태 (정직하게 구분 — 발표/심사에서 이 선을 지킨다)

| 구간 | 상태 |
| --- | --- |
| D15~D17 / P1 / P2 | **실 EC2 리허설 통과**(2026-07-15) — role/credential/egress/audit/scope 경계 실증 |
| D19~D23 | **local/CI e2e 통과**(실 `claude -p` 대상). 단 **GitHub App write 경로는 미검증**(App 미등록), EC2 리허설 없음 |
| P3 (managed MCP) | **CI-locked scaffold만** — 실 AWS role/endpoint/session 없음 |

> 발표에서 피할 표현(strategy.md §7.3): "prompt injection을 해결했다" → "모델이 속아도 sink를 줄이는 경계를 구현했다".
> "D17이 상시 배포됐다" → "fresh EC2 리허설 완료, remote-main 지속 배포는 별개".

## 6. 한 줄로 남길 메시지

> v1은 "AI에 더 많은 걸 시켰다"를 자랑했고, v2는 **"AI의 영향 범위를 증명 가능하게 줄였다"**를 보여준다.
