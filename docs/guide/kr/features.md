# FEATURES — 사용자 기능 리스트 (Slack / 대시보드)

> 사용자가 **직접 할 수 있는 것**만 채널별로 정리. 운영/배포는 [SLACK_GUIDE.md](SLACK_GUIDE.md)·[DASHBOARD_GUIDE.md](DASHBOARD_GUIDE.md).
> 권한: **L0=관찰(즉시 실행)**, **L1=준비(사람 승인 게이트)**. L2(실행)·prod·IAM·DB 변경은 **금지 불변**.

---

## A. Slack — `/devops <명령>`

| # | 기능 | 명령 | 하는 일 | 권한 | 안전장치 |
| --- | --- | --- | --- | --- | --- |
| A1 | 헬스 체크 | `/devops ping` | 에이전트 살아있는지 확인 → `pong`(호스트/버전) | L0 | — |
| A2 | 로그 조회·분석 | `/devops logs <service>` | CloudWatch 로그를 AWS API MCP(read-only)로 가져와 요약·이상 분석 | L0 | 읽기전용 tool allowlist |
| A3 | 종합 진단 | `/devops diagnose <service>` | CloudWatch + kubectl + git diff 다중소스 종합 진단(소스별 실패 격리) | L0 | sanitizer 격리 |
| A4 | Terraform 리뷰 | `/devops tf-review` | `terraform plan` 결과의 리스크·비용·보안 리뷰 (**apply 경로 없음**) | L1 | plan 격리, no-apply |
| A5 | 거버넌스 스캔 | `/devops detect <category>` | iam/config/ssm/incident 카테고리 **read-only AWS 스캔 → findings** | L0 | read-only allowlist |
| A6 | PR 생성 | `/devops pr <설명>` | 브랜치 생성 → 코드 수정 → 단위 테스트 → **diff를 먼저 게시** | L1 | — |

- 채널에 앱 초대 후 사용: `/invite @slackops-devops-agent`
- **A6(pr)은 Slack 동기 경로 미등록** — 출력 게이트가 store 상태를 써서 **job queue(worker) 경유**로만 실행(사람이 diff 승인 후 push/PR). Slack에 치면 "구현 예정" 응답.
- A5(detect)는 Slack/대시보드/스케줄러 모두에서 트리거 가능(실 findings 는 클라우드).

---

## B. 웹 대시보드

| # | 기능 | 화면 | 하는 일 |
| --- | --- | --- | --- |
| B1 | 작업 큐 보기 | Job Queue (`/`) | 모든 작업의 상태(🟡대기/🔵실행/🟢완료/🔴실패)·명령·요청자·비용 목록 |
| B2 | 작업 상세 | `/jobs/[id]` | 기본 정보 + **diff 미리보기** + Audit Timeline(누가 언제 무엇을) |
| B3 | 승인 / 거절 | 작업 상세 | 🟡 대기 작업의 diff 확인 후 **✅ Approve / ❌ Reject** (출력 게이트) |
| B4 | 중복승인 방지 | 작업 상세 | 이미 처리된 작업 재승인 시 "이미 처리된 작업" 거부 = **낙관적 락** |
| B5 | 에이전트 제안 확인 | Job Queue | 🤖 **agent 뱃지 + rationale** — 에이전트가 자율 제안한 작업과 그 근거 |
| B6 | 대화형 요청(채팅) | 상단 채팅 | 자연어 입력(예: `api 5xx 늘었어 원인 봐줘`) → 에이전트 **스트리밍 응답**(Markdown) → 필요 시 작업 **제안** |
| B7 | 텔레메트리 | Telemetry | 실행 횟수·총비용·토큰·도구 호출·성공률 + 명령어별 집계·최근 실행 |
| B8 | 🔔 알림 벨 | 상단바 | 에이전트 자율 제안이 생기면 **벨에 unread 카운트** + 드롭다운(명령·근거·바로가기). "Mark all seen" |
| B9 | 탐지 메뉴 | Detections (`/detections`) | 거버넌스 탐지 카테고리 **ON/OFF + 모드 + Scan now**. 토글은 DynamoDB(CONFIG#detections)에 저장 |

- B6 채팅 입력은 Claude 에 **직접 전달되지 않고** DynamoDB 대화 버스 경유 + sanitizer 격리 → 에이전트는 `propose_job`(read-only)만 호출.
- B3 승인 = "AI가 코드를 만들어도 **사람이 버튼을 눌러야만** 실제 진행"의 핵심 안전장치.
- B9 "Scan now" → `detect` 작업이 큐에 적재 → worker 가 **read-only AWS**(AWS API MCP)로 스캔 → findings 가 작업 결과. **실 findings 는 클라우드(EC2+IAM)에서만**(로컬은 자격증명 부재).

---

## C. 자율 에이전트 (자동 감지 → 알림 → 사람 승인)

| 기능 | 하는 일 | 안전장치 |
| --- | --- | --- |
| **상주 모니터** | EC2 systemd 로 상주(`agent_monitor --loop`). 신호 관찰 → 조치를 큐에 **자율 제안**(L0). | 동일 제안 반복 차단(dedupe 가드) |
| **거버넌스 탐지** | 탐지 메뉴에서 ON + `scheduled` 인 카테고리를 주기적으로 스캔 적재(IAM Access Analyzer·AWS Config·SSM Patch·CloudWatch). | read-only AWS + 사람 게이트 |
| **Slack 작업 알림** | 큐의 **생명주기 이벤트**를 채널에 게시 — 새 작업(누가 web/slack/agent로 명령했는지)·승인 대기·**완료(done)/실패** → 다른 운영자도 인지. `SLACK_NOTIFY_CHANNEL` 설정 시. | 게시만(read-only) |
| **대시보드 알림** | 자율 제안을 **🔔 벨**(B8)로도 표시 — 두 표면, 한 큐. | — |

> 핵심: 에이전트는 *제안·알림*만 하고, **사람이 승인 게이트**를 쥔다. "감지를 발명"하는 게 아니라 *기존 신호/감사를 안전한 조치로* 바꾼다.

---

## D. 공통 / 사용 안 됨

- **이중 컨트롤 플레인** — Slack 과 대시보드가 **단일 job 큐(DynamoDB)** 를 공유(어느 쪽에서 만든 작업이든 양쪽에서 보임). 탐지 토글·findings 도 같은 테이블 → **테이블이 거버넌스 컨트롤 플레인**.
- **사용자가 할 수 없는 것(금지 불변)** — apply/배포, prod 변경, IAM 변경, DB 변경, L2(Execute). 설계상 차단.
