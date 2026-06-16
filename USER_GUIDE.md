# USER_GUIDE — slackops-devops-agent 운영자 가이드

> 운영자(사람)가 **수동으로 입력해야 하는 시크릿/자격증명을 어디에 어떻게 넣는지**와
> 로컬 대시보드 실행, 운영 배포 순서를 한 곳에 모은 문서.
> 코드/아키텍처는 README·docs/ 참조. 표준 배포 절차는 `deploy/README.md`.

---

## 0. 핵심 보안 원칙 (먼저 읽기)
- **EC2 런타임은 AWS Access Key 를 절대 쓰지 않는다** — IAM Instance Profile 만 사용.
  (근거: `harness/CORE_MANDATES.md`, `deploy/ec2/user-data.sh`)
- **로컬 대시보드 기본 모드는 실 AWS 자격증명이 아예 필요 없다** — DynamoDB Local(오프라인).
- Access Key/토큰을 **코드·git 에 하드코딩 금지**. `.env`, `web/.env.local` 은 `.gitignore` 됨.
- 키가 필요한 경우(아래 5번) **최소 권한 + root 계정 키 금지 + 가능하면 임시 자격증명**.

---

## 1. 시크릿 한눈에 — 무엇을 어디에

| 시크릿 | 용도 | 저장 위치 | 발급 방법 |
| --- | --- | --- | --- |
| `SLACK_BOT_TOKEN` (`xoxb-…`) | Slack Bot | **SSM SecureString** `/slackops/SLACK_BOT_TOKEN` | Slack App → OAuth |
| `SLACK_APP_TOKEN` (`xapp-…`) | Socket Mode | **SSM SecureString** `/slackops/SLACK_APP_TOKEN` | Slack App → App-Level Token |
| `CLAUDE_CODE_OAUTH_TOKEN` (`sk-ant-oat…`) | Claude 추론(구독 계정) | **SSM SecureString** `/slackops/CLAUDE_CODE_OAUTH_TOKEN` | `claude setup-token` |
| AWS 자격증명 (EC2 런타임) | AWS/DynamoDB 접근 | **없음** — IAM Instance Profile | `deploy/iam/create-role.sh` |
| AWS 자격증명 (로컬 대시보드, 오프라인) | — | **없음 필요** (DynamoDB Local) | — |
| AWS 자격증명 (Vercel/실 DynamoDB 읽기) | 대시보드가 실 DynamoDB 조회 | **Vercel 환경변수** (또는 로컬 `web/.env.local`) | 최소 권한 IAM 사용자 키 (5번) |

> 핵심: **Slack·Claude 토큰은 EC2 운영용으로 SSM 에**, **AWS 키는 EC2 에선 안 쓰고**(Instance Profile),
> **오직 Vercel/로컬에서 실 DynamoDB 를 읽을 때만** 최소 권한 키가 필요하다.

---

## 2. 로컬 대시보드 빠른 시작 (실 AWS 불필요)
가장 먼저 권장하는 경로 — 오프라인 DynamoDB Local + 시드 데이터.

```sh
cd web
docker compose up --build
```
- 브라우저: **http://localhost:8930**
- 구성: `dynamodb-local`(오프라인) → `seed`(mock Job/Audit/Metric 주입) → `web`.
- **자격증명 입력 불필요** — 더미 키(`local/local`)로 동작.

### 포트 충돌 시
기존 Docker 컨테이너가 8930 을 쓰면 `web/docker-compose.yml` 의 `web.ports` 한 줄만 변경:
```yaml
    ports:
      - "9930:3000"   # 호스트 포트만 교체
```
DynamoDB Local 은 호스트 포트를 노출하지 않으므로(내부 전용) 8000 충돌은 발생하지 않는다.

### 승인 데모
`/` → `pr` 작업(상태 `awaiting_approval`) 클릭 → diff 확인 → **Approve/Reject**.
상태가 `approved`/`rejected` 로 전이되고 audit 타임라인에 이벤트가 추가된다.
(이미 처리된 작업을 다시 승인하면 "이미 처리된 작업입니다" — 낙관적 락 동작 확인.)

---

## 3. Slack 토큰 수동 입력 (운영 — SSM)
Slack App(Socket Mode) 생성 후 토큰을 SSM SecureString 으로 저장한다.
```sh
aws ssm put-parameter --name /slackops/SLACK_BOT_TOKEN --type SecureString --value 'xoxb-...'
aws ssm put-parameter --name /slackops/SLACK_APP_TOKEN --type SecureString --value 'xapp-...'
```
EC2 부팅 시 `user-data.sh` 가 자동 로드 → `/etc/slackops-devops-agent.env`(root 600). 상세: `deploy/README.md` 1단계.

---

## 4. Claude 구독 토큰 수동 입력 (운영 — SSM)
Claude 추론을 **구독 계정**으로 돌린다(AWS 크레딧과 분리). 로컬에서 1회 발급 후 SSM 저장:
```sh
claude setup-token                                  # 구독 로그인 → sk-ant-oat... 출력
aws ssm put-parameter --name /slackops/CLAUDE_CODE_OAUTH_TOKEN --type SecureString --value 'sk-ant-oat...'
```
- EC2 엔 `ANTHROPIC_API_KEY` 를 **두지 않는다**(API 결제 경로 차단). `user-data.sh` 가 OAuth 토큰만 로드.
- 토큰 만료/인증 실패 시: 위 명령으로 재발급 → SSM 갱신 → `sudo systemctl restart slackops-devops-agent`.

---

## 5. AWS Access Key 수동 입력 — *오직 실 DynamoDB 를 읽을 때만*
로컬 오프라인 모드(2번)에는 **불필요**. 아래는 **Vercel 배포 대시보드**(또는 로컬에서 실 DynamoDB 를
보고 싶을 때)가 실 DynamoDB 를 읽기 위한 **최소 권한 IAM 사용자 키** 발급/입력 절차다.

### 5-1. 최소 권한 IAM 사용자 생성
IAM → Users → Create user(콘솔 접근 OFF, 프로그래매틱 전용) → 아래 인라인 정책 부여.
대시보드 읽기 전용이면 read-only, 대시보드에서 approve/reject(쓰기)까지 하려면 UpdateItem/PutItem 포함.

읽기 전용 정책(권장 — 심사용 대시보드):
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
생성한 사용자 → Security credentials → **Create access key** → "Application running outside AWS" →
`AKIA...` / `secret` 확보. **secret 은 이때만 보인다 — 안전히 보관, git 금지.**

### 5-3. 입력 위치
- **Vercel(권장 — 제출용):** 프로젝트 → Settings → Environment Variables 에 추가:
  | Key | Value |
  | --- | --- |
  | `DDB_TABLE` | `slackops-agent` |
  | `AWS_REGION` | `ap-northeast-2` (테이블 생성 리전과 일치) |
  | `AWS_ACCESS_KEY_ID` | `AKIA...` |
  | `AWS_SECRET_ACCESS_KEY` | `...` |
  | `DASHBOARD_APPROVER` | 표시할 승인자명 |

  ⚠️ **`DDB_ENDPOINT` 는 설정하지 않는다** — 미설정 시 실 DynamoDB 로 연결된다.

- **로컬에서 실 DynamoDB 확인:** `web/.env.local.example` → `web/.env.local` 복사 후
  "모드 B" 블록을 채운다(`DDB_ENDPOINT` 줄 삭제/주석). `.env.local` 은 커밋되지 않는다.

### 5-4. 키 회전/폐기
심사 종료 후 또는 노출 의심 시 IAM → 해당 키 **Deactivate → Delete**. 새 키로 교체.

---

## 6. 운영 배포 순서 (요약 — 상세 deploy/README.md)
1. Slack App 생성 + SSM 토큰 저장(3번) + Claude 토큰(4번)
2. `deploy/iam/create-role.sh` — IAM Role + Instance Profile
3. `deploy/dynamodb/create-table.sh` — DynamoDB 테이블(온디맨드)
4. `deploy/ec2/launch-instance.sh` — EC2 기동(`REPO_URL` 교체)
5. `deploy/eventbridge/create-schedules.sh <instance-id>` — 스케줄 가동
6. `/devops ping` e2e 확인
7. Vercel 대시보드 배포(5-3) + 실 DynamoDB 연결

---

## 7. 해커톤 심사기간 비용 절약 (6/29 제출 ~ 7/24 심사)
심사는 제출물(데모영상·Vercel 링크·DynamoDB 스크린샷)로 진행 — **EC2 상시 가동 불필요**.
- ✅ **유지:** Vercel 대시보드(무료) + DynamoDB 테이블(온디맨드 ~$0)
- ❌ **끔(stop):** EC2 에이전트 — 필요 시 start. c7i.large 상시 가동은 크레딧을 소진한다.
