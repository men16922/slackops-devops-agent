# USER_GUIDE — slackops-devops-agent (운영자 + 대시보드 가이드)

> **한 문서, 두 독자.** ① **대시보드를 보고 누르는 사람** → §2. ② **배포·시크릿을 다루는 운영자** → §0·§1·§3~§7.
> 코드/아키텍처는 README·docs/ 참조. 표준 배포 절차는 `deploy/README.md`. 직접 검증 항목은 [QA_LIST.md](QA_LIST.md).

---

## 0. 핵심 보안 원칙 (먼저 읽기)
- **EC2 런타임은 AWS Access Key 를 절대 쓰지 않는다** — IAM Instance Profile 만(`harness/CORE_MANDATES.md`, `deploy/ec2/user-data.sh`).
- **로컬 대시보드 기본 모드는 실 AWS 자격증명이 아예 필요 없다** — DynamoDB Local(오프라인).
- Access Key/토큰을 **코드·git 에 하드코딩 금지**. `.env`, `web/.env.local` 은 `.gitignore` 됨.
- 키가 필요한 경우(§5) **최소 권한 + root 계정 키 금지 + 가능하면 임시 자격증명**.

---

## 1. 시크릿 한눈에 — 무엇을 어디에

| 시크릿 | 용도 | 저장 위치 | 발급 |
| --- | --- | --- | --- |
| `SLACK_BOT_TOKEN` (`xoxb-…`) | Slack Bot | **SSM SecureString** `/slackops/SLACK_BOT_TOKEN` | Slack App → OAuth |
| `SLACK_APP_TOKEN` (`xapp-…`) | Socket Mode | **SSM SecureString** `/slackops/SLACK_APP_TOKEN` | Slack App → App-Level Token |
| `CLAUDE_CODE_OAUTH_TOKEN` (`sk-ant-oat…`) | Claude 추론(구독) | **SSM SecureString** `/slackops/CLAUDE_CODE_OAUTH_TOKEN` | `claude setup-token` |
| AWS 자격증명 (EC2 런타임) | AWS/DynamoDB 접근 | **없음** — IAM Instance Profile | `deploy/iam/create-role.sh` |
| AWS 자격증명 (로컬 대시보드) | — | **불필요** (DynamoDB Local) | — |
| AWS 자격증명 (Vercel/실 DynamoDB 읽기) | 대시보드가 실 DynamoDB 조회 | **Vercel 환경변수** / 로컬 `web/.env.local` | 최소 권한 IAM 키 (§5) |

> 핵심: **Slack·Claude 토큰은 EC2 운영용으로 SSM 에**, **AWS 키는 EC2 에선 안 쓰고**(Instance Profile),
> **오직 Vercel/로컬에서 실 DynamoDB 를 읽을 때만** 최소 권한 키가 필요하다.

---

## 2. 로컬 대시보드 — 빠른 시작 + 화면 사용법 (실 AWS 불필요)

### 2.1 기동
```sh
cd web
docker compose up --build
```
- 브라우저: **http://localhost:8930**
- 구성: `dynamodb-local`(오프라인) → `seed`(mock Job/Audit/Metric) → `web`. **자격증명 불필요**(더미 키).
- 포트 8930 충돌 시 `web/docker-compose.yml` 의 `web.ports` 한 줄만 교체(예: `"9930:3000"`).

### 2.2 화면 읽는 법
상단 메뉴 2개 — **Job Queue**(명령 목록·상태) / **Telemetry**(사용량 통계).

| 뱃지 | 뜻 | 할 일 |
| --- | --- | --- |
| 🟡 `awaiting_approval` | 사람 승인 대기 | **클릭해서 확인** |
| 🔵 `running` | 실행 중 | 기다리기 |
| 🟢 `done` | 완료 | — |
| 🔴 `failed` | 실패 | 상세에서 원인 확인 |

- 파란 **명령어 글씨**(`pr`/`diagnose`/`logs`) 클릭 → 상세 화면.
- 🤖 **agent 뱃지 + rationale** = 에이전트가 자율 제안한 작업(왜 제안했는지 근거 표시).

### 2.3 작업 상세 + 승인 데모 ⭐ (안전장치 핵심)
작업 클릭 → 기본 정보(명령/요청자/비용/토큰) + 맨 아래 **Audit Timeline**.
🟡 승인 대기 작업이면 **📝 diff 미리보기 + ✅ Approve / ❌ Reject**.

1. 🟡 작업 클릭 → diff 읽기 → ✅ **Approve** → 상태 `approved` + 타임라인에 "누가 언제 승인".
2. 새로고침 후 **같은 작업 재승인** → **"이미 처리된 작업"** 거부 = **낙관적 락**(중복 실행 방지) 동작.

> **AI가 코드를 만들어도, 사람이 버튼을 눌러야만 실제로 진행된다** — 출력 게이트(주입 방어 3계층).

### 2.4 웹에서 직접 명령 보내기
첫 화면 상단 입력칸: **드롭다운**(`logs`/`diagnose`/`tf-review`/`pr`/`ping`) + **인자칸** → **Send**.
→ 목록 맨 위 `pending` 등장. 🔒 자유 문장이 아니라 **정해진 명령+인자**로만 받음(모르는 명령 거부 = 주입 방어).

### 2.5 전체 실행 루프 — 에이전트 제안 → 승인 → **실제 실행**
제안/승인 뒤 **실제 실행**까지 보려면 worker 를 띄운다(실 Claude — `CLAUDE_CODE_OAUTH_TOKEN` 필요).
```sh
make agent-monitor                           # 에이전트가 신호 감지 → 제안(pending)
# 웹 8930 에서 제안 Approve
export CLAUDE_CODE_OAUTH_TOKEN="$(claude setup-token)"
make worker ARGS=--once                       # 승인분 실제 실행 → done + audit/metric 반영
```
- L0(diagnose)는 즉시 실행→`done`, L1(pr)은 prepare→`awaiting_approval`, 승인분은 execute→`done`.
- 검증 체크리스트는 [QA_LIST.md](QA_LIST.md) §3, 루프 상세는 `docs/runbooks/agent-mcp-demo.md`.

### 2.6 Telemetry — 사용량 통계
위쪽 카드(실행 횟수/총비용/토큰/도구 호출/성공률) + 아래 명령어별 집계·최근 실행. 비용은 보통 한 번에 몇 센트.

### 2.7 FAQ
- **목록이 비어요** — 시드 미주입/DB 연결 끊김. 잠시 후 새로고침.
- **버튼이 거부돼요** — 이미 다른 사람이 먼저 승인/거부했거나 상태가 바뀜(정상, 낙관적 락).
- **데이터가 진짜인가요?** — 기본은 **샘플 시드**. 실 운영/배포 시 Slack·에이전트 명령이 실시간 적재.
- **끄기** — `cd web && docker compose down`. 메모리 DB라 끄면 사라지고 다시 켜면 시드 재생성.

---

## 3. Slack 토큰 수동 입력 (운영 — SSM)
Slack App(Socket Mode) 생성 후:
```sh
aws ssm put-parameter --name /slackops/SLACK_BOT_TOKEN --type SecureString --value 'xoxb-...'
aws ssm put-parameter --name /slackops/SLACK_APP_TOKEN --type SecureString --value 'xapp-...'
```
EC2 부팅 시 `user-data.sh` 가 자동 로드 → `/etc/slackops-devops-agent.env`(root 600). 상세: `deploy/README.md` 1단계.

---

## 4. Claude 구독 토큰 수동 입력 (운영 — SSM)
Claude 추론을 **구독 계정**으로(AWS 크레딧과 분리). 1회 발급 후 SSM 저장:
```sh
claude setup-token                                  # 구독 로그인 → sk-ant-oat... 출력
aws ssm put-parameter --name /slackops/CLAUDE_CODE_OAUTH_TOKEN --type SecureString --value 'sk-ant-oat...'
```
- EC2 엔 `ANTHROPIC_API_KEY` 를 **두지 않는다**(API 결제 경로 차단). `user-data.sh` 가 OAuth 토큰만 로드.
- 만료/인증 실패 시: 재발급 → SSM 갱신 → `sudo systemctl restart slackops-devops-agent`.

---

## 5. AWS Access Key 수동 입력 — *오직 실 DynamoDB 를 읽을 때만*
로컬 오프라인 모드(§2)에는 **불필요**. 아래는 **Vercel 배포 대시보드**(또는 로컬에서 실 DynamoDB 조회)가
실 DynamoDB 를 읽기 위한 **최소 권한 IAM 사용자 키** 절차다.

### 5-1. 최소 권한 IAM 사용자
IAM → Users → Create user(콘솔 접근 OFF, 프로그래매틱 전용) → 인라인 정책. 읽기 전용(권장 — 심사용):
```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Sid": "DashboardRead",
    "Effect": "Allow",
    "Action": ["dynamodb:GetItem", "dynamodb:Query"],
    "Resource": [
      "arn:aws:dynamodb:*:*:table/slackops-agent",
      "arn:aws:dynamodb:*:*:table/slackops-agent/index/*"
    ]
  }]
}
```
대시보드 승인(쓰기)까지 허용하려면 `Action` 에 `"dynamodb:UpdateItem", "dynamodb:PutItem"` 추가.

### 5-2. 액세스 키 발급
사용자 → Security credentials → **Create access key** → "Application running outside AWS" →
`AKIA...`/`secret` 확보. **secret 은 이때만 보인다 — 안전 보관, git 금지.**

### 5-3. 입력 위치
- **Vercel(권장 — 제출용):** Settings → Environment Variables:
  | Key | Value |
  | --- | --- |
  | `DDB_TABLE` | `slackops-agent` |
  | `AWS_REGION` | `ap-northeast-2` (테이블 생성 리전과 일치) |
  | `AWS_ACCESS_KEY_ID` | `AKIA...` |
  | `AWS_SECRET_ACCESS_KEY` | `...` |
  | `DASHBOARD_APPROVER` | 표시할 승인자명 |

  ⚠️ **`DDB_ENDPOINT` 는 설정하지 않는다** — 미설정 시 실 DynamoDB 로 연결된다.
- **로컬에서 실 DynamoDB 확인:** `web/.env.local.example` → `web/.env.local` 복사 후 "모드 B" 블록 채움(`DDB_ENDPOINT` 줄 삭제/주석). `.env.local` 은 커밋되지 않는다.

### 5-4. 키 회전/폐기
심사 종료 후 또는 노출 의심 시 IAM → 키 **Deactivate → Delete** → 새 키 교체.

---

## 6. 운영 배포 순서 (요약 — 상세 deploy/README.md, 실행 런북 action_item.md)
1. Slack App 생성 + SSM 토큰(§3) + Claude 토큰(§4)
2. `deploy/iam/create-role.sh` — IAM Role + Instance Profile
3. `deploy/dynamodb/create-table.sh` — DynamoDB 테이블(온디맨드)
4. `deploy/ec2/launch-instance.sh` — EC2 기동(`REPO_URL` 교체)
5. `deploy/eventbridge/create-schedules.sh <instance-id>` — 스케줄 가동
6. `/devops ping` e2e 확인
7. Vercel 대시보드 배포(§5-3) + 실 DynamoDB 연결

---

## 7. 해커톤 심사기간 비용 절약 (6/29 제출 ~ 심사 6/30~)
심사는 제출물(데모영상·Vercel 링크·DynamoDB 스크린샷)로 진행 — **EC2 상시 가동 불필요**.
- ✅ **유지:** Vercel 대시보드(무료) + DynamoDB 테이블(온디맨드 ~$0)
- ❌ **끔(stop):** EC2 에이전트 — 필요 시 start. c7i.large 상시 가동은 크레딧을 소진한다.
