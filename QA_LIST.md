# QA_LIST — 직접 검증 체크리스트 (P1 로컬 e2e 우선)

최종 갱신: 2026-06-18

> **사람(운영자/제출자)이 직접 눈으로 확인해야 하는 것**을 모은 문서.
> 자동 게이트(pytest/ruff/mypy)가 검증하는 코드 정합은 여기 없다 — 그건 `make check`(250 passed).
> 여기는 **사람만 판단 가능한 것**(실제 동작·UX·실측치·심사 충족)만 다룬다.
> 실행 방법 상세는 [USER_GUIDE.md](USER_GUIDE.md), 에이전트 루프는 [docs/runbooks/agent-mcp-demo.md](docs/runbooks/agent-mcp-demo.md).

---

## 0. 지금 프로젝트가 한 일 / 목표 (오리엔테이션)

**한 줄:** Slack-controlled DevOps agent — Slack/웹 자연어 명령을 EC2의 Claude Code Headless가
안전 게이트를 거쳐 AWS/K8s/Terraform/GitHub 컨텍스트로 분석·자동화한다.

**무엇을 만들었나 (현재):**
- **이중 컨트롤 플레인** — Slack(Socket Mode) + 웹 대시보드(Next.js/Vercel)가 **단일 job 큐(DynamoDB 단일테이블)** 를 공유.
- **권한 게이트** — Level 0(관찰)/1(준비·PR) 만 활성, L2(실행)·prod·IAM·DB 변경 **금지 불변**.
- **주입 방어 4계층** — Sanitizer(untrusted 격리) / Tool Allowlist / 출력 게이트(diff 사람 승인) / Template Prompt.
- **전체 OTel 계측** — 실행 1건당 latency/토큰/비용(USD)/tool-call.
- **에이전트 자율 제안 루프(D9)** — 에이전트가 신호 감지 → MCP `propose_job`로 큐에 제안 → 사람이 웹에서 승인.
- **풀 루프 로컬 완결** — `agent_monitor`(감지) → 웹 Approve → `worker`(실행) 까지 로컬에서 닫힘.

**목표(MVP 범위):** Read-Only 분석 + PR 생성까지. **차별화 축 = 보안(최소권한 + 주입방어) + 계측(OTel).**
"단순 봇"이 아니라 **"에이전트를 안전하게 운영하는 법"의 레퍼런스**.

**지금 단계:** 로컬 코드·웹·풀 루프 완성. 남은 건 전부 `[manual]` — AWS 배포 + 실측 캡처 + 제출물(6/29).

---

## 1. 유저 입장 장점 (대상: 소규모 팀의 DevOps/플랫폼 엔지니어·온콜)

| 장점 | 설명 |
| --- | --- |
| **콘솔 안 켜고 Slack 한 줄로 진단** | `/devops diagnose api` → CloudWatch+kubectl+git diff 종합 진단. 온콜 토일 감소. |
| **AI가 prod를 멋대로 못 건드림** | 코드 변경(PR)은 **diff를 사람이 보고 승인**해야만 진행. 금지 불변(배포/IAM/DB) 하드 차단. |
| **에이전트가 먼저 알려줌** | 에이전트가 이상 신호를 감지해 작업을 **제안**(사람 승인 대기) — 수동 감시 부담 감소. |
| **비용·시간 투명** | 매 실행의 토큰/비용/소요를 대시보드에서 확인(보통 한 번에 몇 센트). |
| **자격증명 안 쌓임** | EC2는 IAM Instance Profile만 — Access Key 저장·커밋 0. 인바운드 포트 0(Socket Mode). |

---

## 2. 해커톤 심사 4축 충족 매핑 (Devpost 기준, 심사 6/30)

| 축 | 우리 충족 근거 |
| --- | --- |
| **① Technical Implementation** (DB가 의도적·실 엔지니어링인가) | DynamoDB **단일테이블** + **conditional write 로 atomic claim / optimistic-lock 승인게이트**(별도 코디네이터 불필요). GSI2 = FEED/AUDIT/METRIC 피드. **한 문장 정당화:** *"두 control plane(Slack+Vercel)이 단일 job 큐를 공유 — DynamoDB conditional write로 별도 코디네이터 없이 atomic claim과 중복승인 차단(낙관적 락)을 얻는다."* |
| **② Design** (프론트-백 정합·풀스택 사고) | 웹 TS `lib/ddb`가 파이썬 `store/`의 단일테이블 계약을 **미러**(GSI 질의 동형), 승인 server action이 파이썬 `_conditional_set` ConditionExpression을 **미러**. |
| **③ Impact & Real-World** (출시 가능? 구체 대상 실문제?) | 대상 = **소규모 팀 온콜/플랫폼 엔지니어**. 실문제 = 콘솔 왕복·수동 진단 토일. 출시성 = Socket Mode(공개 포트 0)+최소권한+사람 승인 게이트로 안전 운영 가능. |
| **④ Originality** (스택으로 가능한 통찰) | **에이전트 자율 제안 + 사람 승인**이 단일 큐를 공유하는 control plane — "AI가 운영을 *제안*하고 사람이 *경계*를 쥔다". 단순 챗봇이 아니라 안전 운영 패턴의 레퍼런스. |

> 심사위원은 **앱을 직접 안 돌릴 수 있음** → **데모영상 + 제출 설명**이 큰 비중. 이 QA가 그 영상/설명의 실증 근거다.
> **보너스 +0.6:** 6/29 전 아티클/영상 발행 + `#H0Hackathon`.

---

## 3. ★ 내가 지금 직접 검증할 것 — 로컬 풀 e2e (P1)

> 준비물: **Docker 데몬** + **Claude 구독 토큰**(`claude setup-token`). AWS 자격증명 **불필요**(DynamoDB Local).
> 상세 절차: [docs/runbooks/agent-mcp-demo.md](docs/runbooks/agent-mcp-demo.md) "전체 실행 루프".

### 3-A. 대시보드 기동 + 화면 (토큰 불필요)
```bash
cd web && docker compose up -d --build      # 8930=대시보드, 8931=DynamoDB Local
```
- [ ] http://localhost:8930 접속 → Job Queue에 **시드 작업 목록**이 보인다.
- [ ] 🤖 **agent 뱃지 + rationale(제안 근거)** 가 붙은 작업이 보인다(에이전트 제안 샘플).
- [ ] 🟡 `awaiting_approval` 작업 클릭 → **diff 미리보기 + Approve/Reject** 버튼이 보인다.
- [ ] **Approve** → 상태 `approved` 전이 + Audit 타임라인에 "누가 언제 승인" 기록.
- [ ] 새로고침 후 **같은 작업 재승인 시도** → "이미 처리된 작업" 거부(= **낙관적 락** 동작).
- [ ] **Telemetry** 탭 → 실행 횟수/총비용/토큰/성공률 카드 + 명령별 집계.
- [ ] 첫 화면 상단 **명령 입력칸**(드롭다운+인자) → `diagnose`+`api` Send → 목록 맨 위 `pending` 등장(웹 producer).

### 3-B. 에이전트 자율 제안 (토큰 불필요 — Tier1 시뮬)
```bash
make agent-monitor                          # 기본 데모 신호(504 spike)로 제안 1건 적재
```
- [ ] 로그에 `monitor.sim.proposed` + command/rationale 출력.
- [ ] 대시보드 피드 최상단에 🤖 agent 제안(diagnose)이 `pending`으로 뜬다.

### 3-C. 승인 → 실제 실행 풀 루프 (★ 토큰 필요 — 실 Claude)
```bash
export CLAUDE_CODE_OAUTH_TOKEN="$(claude setup-token)"
make worker ARGS=--once                      # 승인/대기 job 1건 실제 실행 (실 Claude)
```
- [ ] `diagnose` 작업이 `pending`/`approved` → `running` → **`done`** 으로 전이.
- [ ] 결과에 **실제 Claude 진단 텍스트**가 채워짐(로컬에선 git diff 소스가 주재료 — 아래 주의).
- [ ] 대시보드 상세에 **비용/토큰 실측치** + Audit `claimed`/`done` 기록.
- [ ] Telemetry에 실행 1건 반영(실 토큰/비용).

> **주의(예상 동작):** 로컬 diagnose는 CloudWatch·kubectl 소스가 자격증명/클러스터 부재로 **실패 격리**되고
> **git diff 소스**로 Claude가 진단한다 — "다중소스 + 소스별 실패격리 + 실 Claude 호출"을 확인하기엔 충분.
> **L1(pr)의 execute는 실제 `git push`+`gh pr create`** 를 시도하므로 로컬 데모는 **L0(diagnose)** 로 한다.

---

## 4. 내가 직접 검증할 것 — AWS 배포 후 (P4, 나중)

> 로컬에선 "설명"일 뿐, AWS에서만 "실증"되는 차별화 축. 상세 [USER_GUIDE.md](USER_GUIDE.md) §6 + action_item.md.

- [ ] **Socket Mode 인바운드 0** — EC2 SG에 인바운드 규칙 없이 `/devops ping` → `pong`(스크린샷).
- [ ] **IAM Instance Profile** — EC2에 Access Key 없이 CloudWatch RO/SSM Read 동작(role 캡처).
- [ ] **실 DynamoDB** — `slackops-agent` 테이블 ACTIVE + 실 항목(Job/Audit/Metric) 콘솔 캡처.
- [ ] **실측 수치** — diagnose 1회: 소요 N초 / 비용 $0.0X / tool call M회(CloudWatch/X-Ray).
- [ ] **EventBridge** — 평일 stop/start 스케줄 동작(상시 가동 금지 = 비용 통제).
- [ ] **출력 게이트 + branch protection** — 승인 없이 머지 불가(실 GitHub).
- [ ] **Vercel 대시보드** — 실 DynamoDB 읽어 피드 렌더 + Team ID/링크 확보.

---

## 5. 알려진 한계 / 주의 (제출 설명에 정직히)

- DynamoDB Local은 **in-memory** — `docker compose down` 시 데이터 소멸, `up` 시 시드 재주입.
- `tool_calls` 계측은 현재 `None`(stream-json 파싱 도입 전 — 의도된 결정).
- L2(Execute)/prod/IAM/DB 변경은 **비활성**(금지 불변) — MVP 범위 밖.
- 로컬 worker의 pr execute는 실 push라 GitHub 인증 환경(=AWS/EC2)에서만 검증.
- SQLite는 **MVP/테스트 한정** — prod 데이터스토어로 호칭하지 않는다(운영 = DynamoDB).
