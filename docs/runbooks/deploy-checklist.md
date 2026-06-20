# 배포 체크리스트 — AWS + Vercel + Slack (H0 제출용)

최종 갱신: 2026-06-20
대상 repo: https://github.com/men16922/slackops-devops-agent (private)

> **목적:** 로컬 코드는 완성·검증됨(`pytest` 274 passed · ruff · mypy strict · web `next build` green).
> 남은 건 전부 **운영자 수동 단계**(유효 AWS 자격증명 + Slack/Vercel 계정 필요). 이 문서는
> NEXT_PLAN 의 `[manual]` 항목을 **위→아래 실행 순서**로 한 번에 풀어 쓴 단일 체크리스트다.
> 권위 순서(충돌 시): `deploy/README.md` + 각 스크립트 원문 > 이 문서. 운영자 가이드: 루트 `SLACK_GUIDE.md`(에이전트)·`DASHBOARD_GUIDE.md`(대시보드).
> 비용: AWS 크레딧 신청 **거절** → 보유 **$63.91 + 무료티어**로 진행. 심사기간 EC2 stop 시 ~$0.

---

## 0. 전체 흐름 한눈에

```
[준비] 자격증명·리전 고정
   ▼
[A] Slack App 생성 + SSM 토큰 저장        (Slack UI + aws ssm)
   ▼
[B] AWS 인프라  IAM → DynamoDB → EC2 → EventBridge   (deploy/*.sh, 순서 고정)
   ▼
[C] e2e 검증    /devops ping → pong + 스크린샷
   ▼
[D] Vercel 배포  읽기전용 IAM 키 → web/ 배포 → 링크/Team ID   ← 제출 필수
   ▼
[E] 실데이터·수치  diagnose 1회 → DynamoDB 콘솔 캡처 + N초/$0.0X/tool call
   ▼
[F] 제출물 마감  EC2 stop, DynamoDB·Vercel 유지
```

**의존성:** `[A]` 는 `[B]`-EC2 **이전** 필수(부팅 시 SSM 토큰 로드). `[B]` 는 IAM→DynamoDB→EC2 **순서 고정**.
`[D]` Vercel 은 `[B]`-DynamoDB 만 있으면 `[C]` 와 무관하게 병렬 가능.

**검증 전략(중요):** 기능 검증은 **로컬에서 전부 가능** — Slack(Socket Mode)→EC2→DynamoDB→worker 풀루프 +
로컬 web 대시보드(DASHBOARD_GUIDE §1~§6, `make demo`/docker compose). **Vercel 은 검증용이 아니라 제출물**
(공개 링크+Team ID 가 H0 필수) → **로컬 검증을 다 끝낸 뒤 제출 직전에 1회 배포**한다.
비용: Vercel **Hobby 무료**(100GB/월·비상업 — 추가 비용 0). AWS 비용 추정 = 부록 2.

---

## 사전 준비 (Prerequisites)

- [x] **AWS 자격증명 유효** — `aws sts get-caller-identity` 로 Account/Arn 출력 확인.
      (현재 로컬 자격증명 무효 → `aws configure` 또는 `aws sso login` 으로 갱신.)
- [x] **리전 고정** — `us-east-1` 기준(Python 코드 기본값과 일치). EC2 도 같은 리전에 기동.
      한 번 정하면 이후 전부 동일하게(create-table·Vercel env·EC2 launch).
      ```sh
      export AWS_REGION=us-east-1
      ```
- [x] **로컬 도구** — `aws` CLI v2, `git`, `node`/`npm`(Vercel), `claude` CLI(구독 토큰 발급).
- [x] **계정** — Slack 워크스페이스(앱 생성 권한), Vercel 계정.

> **시크릿 원칙(불변):** 토큰/키는 **절대 repo·.env 커밋 금지**. 운영 토큰은 SSM SecureString,
> Vercel 키는 Vercel 환경변수에만. EC2 런타임은 **IAM Instance Profile 만**(Access Key 금지).

---

## [A] Slack App 생성 + SSM 토큰 저장

> 결과물: `SLACK_BOT_TOKEN`(xoxb-…), `SLACK_APP_TOKEN`(xapp-…), `CLAUDE_CODE_OAUTH_TOKEN`(sk-ant-oat…) → SSM.
> Socket Mode 라 **인바운드 URL 불필요**(공개 엔드포인트 없음 = 보안 불변).

### A-1. Slack App (https://api.slack.com/apps)
- [x] **Create New App → From scratch** → 이름 `slackops-devops-agent`, 워크스페이스 선택.
- [x] **Socket Mode** → Enable 토글 ON → App-Level Token scope `connections:write` 생성
      → 출력 `xapp-…` = **`SLACK_APP_TOKEN`**.
- [x] **OAuth & Permissions → Bot Token Scopes**: `commands`, `chat:write`, (선택)`chat:write.public`.
- [x] **Slash Commands → Create New Command**: `/devops`,
      Usage Hint `ping | logs <svc> | diagnose <svc> | tf-review | pr <설명>` (Request URL 칸은 비움).
- [x] **Install to Workspace** → 승인 → **Bot User OAuth Token** `xoxb-…` = **`SLACK_BOT_TOKEN`**.

### A-2. Claude 구독 토큰 발급 (추론비를 구독 계정에 귀속 — AWS 크레딧과 분리)
- [x] 로컬에서 장수명 토큰 발급:
      ```sh
      claude setup-token        # 구독 로그인 → sk-ant-oat... 출력
      ```

### A-3. SSM SecureString 저장
```sh
aws ssm put-parameter --name /slackops/SLACK_BOT_TOKEN          --type SecureString --value 'xoxb-...'
aws ssm put-parameter --name /slackops/SLACK_APP_TOKEN          --type SecureString --value 'xapp-...'
aws ssm put-parameter --name /slackops/CLAUDE_CODE_OAUTH_TOKEN  --type SecureString --value 'sk-ant-oat...'
```
- [x] 검증 완료(2026-06-20, region `us-east-1`, account `908601828278`): 3개 모두 복호화 prefix 확인 — `xoxb-`/`xapp-1-`/`sk-ant-oat01`.
      ```sh
      aws ssm get-parameter --name /slackops/SLACK_BOT_TOKEN --with-decryption \
        --query Parameter.Value --output text | head -c 8     # "xoxb-..." 앞부분
      ```

---

## [B] AWS 인프라 — IAM → DynamoDB → EC2 → EventBridge

> 모든 스크립트는 `deploy/` 에서 실행. **순서 고정**(EC2 부팅 시 Instance Profile 로 DynamoDB·SSM 접근).

### B-1. IAM Role + Instance Profile — `deploy/iam/create-role.sh`
읽기전용(CloudWatch/Logs/EKS Describe/SSM Read/S3 Read) + OTel export 최소쓰기 + DynamoDB 테이블 스코프(Get/Put/Update/Query).
```sh
( cd deploy/iam && ./create-role.sh )
# → OK: role=slackops-devops-agent-role profile=slackops-devops-agent-profile
```
- [x] 검증 완료(2026-06-20): role→profile 연결 + 인라인 정책 `slackops-devops-agent-ro` 확인.
      ```sh
      aws iam get-instance-profile --instance-profile-name slackops-devops-agent-profile \
        --query 'InstanceProfile.Roles[0].RoleName' --output text
      ```
> ⚠️ **멱등 아님** — 이미 있으면 `EntityAlreadyExists`. 재실행 시 기존 role/profile 정리 후(부록 2).

### B-2. DynamoDB 단일테이블 — `deploy/dynamodb/create-table.sh`
**온디맨드(PAY_PER_REQUEST)** — bursty·저빈도라 용량계획 불필요·idle 시 ~0원, GSI 자동 상속. **멱등**(있으면 생략).
```sh
( cd deploy/dynamodb && AWS_REGION=us-east-1 ./create-table.sh )
# → OK: table 'slackops-agent' created (PAY_PER_REQUEST, GSI1+GSI2)
```
- [x] 검증 완료(2026-06-20, us-east-1): **Status=ACTIVE, Billing=PAY_PER_REQUEST, GSIs=2**.
      ```sh
      aws dynamodb describe-table --table-name slackops-agent \
        --query 'Table.{Status:TableStatus,Billing:BillingModeSummary.BillingMode,GSIs:length(GlobalSecondaryIndexes)}'
      # → Status=ACTIVE, Billing=PAY_PER_REQUEST, GSIs=2
      ```
- [ ] **DynamoDB 콘솔 스크린샷** 미리 1장(제출물). 실 항목은 [E] 후 다시.

### B-3. EC2 기동 — `deploy/ec2/launch-instance.sh`
c7i.large, 최신 AL2023, IMDSv2 강제, **인바운드 0 SG**(아웃바운드 전용). user-data 가 도구체인 설치 + systemd **3개** 등록
(`slackops-devops-agent`=Slack앱 · `-worker`=승인 job 실행 · `-chat-agent`=웹 채팅 응답).
> `REPO_URL` 기본값은 이미 `men16922` repo — sed 교체 불필요.
> ⚠️ **private repo clone 주의:** user-data 의 `git clone` 은 무인증. 택1 →
> (가장 단순) 데모용 **public 전환** · SSM 에 GitHub PAT 저장 후 `https://<token>@github.com/...` · deploy key(SSH).
```sh
INSTANCE_ID="$( cd deploy/ec2 && ./launch-instance.sh )"
echo "$INSTANCE_ID"                                   # i-xxxxxxxx
aws ec2 wait instance-running --instance-ids "$INSTANCE_ID"
aws ec2 get-console-output --instance-id "$INSTANCE_ID" --query Output --output text | tail -40
```
- [x] 기동 완료(2026-06-20): **`i-0b0f56487fd7ff0bf`** (us-east-1b, c7i.large, profile 연결). repo는 데모용 **public 전환**으로 무인증 clone. 역할에 `AmazonSSMManagedInstanceCore` 부착(Session Manager 접속용, 인바운드 0 유지).

### B-4. EventBridge 스케줄 — `deploy/eventbridge/create-schedules.sh`
EC2 stop/start(상시 가동 금지 불변). 기본 평일 09:00 start / 19:00 stop (Asia/Seoul).
```sh
( cd deploy/eventbridge && ./create-schedules.sh "$INSTANCE_ID" )
# → OK: schedules created for i-xxxx (Asia/Seoul)
```
> 데모 직전엔 스케줄과 무관하게 running 확인: `aws ec2 start-instances --instance-ids "$INSTANCE_ID"`

---

## [C] e2e 검증 — `/devops ping`

> 결과물: Slack → EC2 → pong 왕복 1회(코드의 마지막 미검증 경로) + 스크린샷.
> 접속은 SSH 대신 **SSM Session Manager**(인바운드 0 유지): `aws ssm start-session --target "$INSTANCE_ID"`.

- [x] **서비스 3개 active**(2026-06-20, SSM send-command 확인): slack/worker/chat-agent 모두 `active`,
      `cloud-init status: done`, health `{"status":"ok"}`, 도구체인(claude/kubectl/terraform/gh/helm/jq) 설치 확인.
      ```sh
      systemctl status slackops-devops-agent slackops-devops-agent-worker slackops-devops-agent-chat-agent
      curl 127.0.0.1:8080/health        # {"status":"ok"}
      ```
- [x] **Slack e2e 성공**(2026-06-20): `/devops ping` → `:white_check_mark: pong — slackops-devops-agent v0.0.0
      on ip-172-31-4-86.ec2.internal (python 3.11.15)`. hostname=EC2 내부 → 클라우드 왕복 확인. (스크린샷 = 제출 footage)
- [ ] 무응답 시 `journalctl -u slackops-devops-agent -n 50`(Socket 연결/토큰 로드) → 부록 1.

---

## [D] Vercel 배포 — 대시보드 공개 링크 (제출 필수, **로컬 검증 후 마지막에**)

> 결과물: 실 DynamoDB 를 읽는 Next.js 대시보드 + **Published Vercel Link + Team ID**.
> **이 단계는 기능 검증이 아니라 제출 아티팩트 확보용** — 로컬 web 대시보드로 검증을 끝낸 뒤 제출 직전에 1회 배포.
> 비용: **Hobby 무료 플랜으로 충분**(bandwidth 100GB/월·서버리스 포함·비상업 = 해커톤 OK). 카드 불필요.
> 구조: 브라우저 → Vercel(Next.js 서버) → **AWS SDK + 읽기전용 키** → DynamoDB 읽기. (EC2 아님 → Instance Profile 불가라 여기서만 Access Key 사용 = 읽기전용·테이블 스코프.)

### D-1. Vercel 전용 읽기전용 IAM 사용자 키 (DASHBOARD_GUIDE §7)
IAM → Users → Create user(콘솔 OFF, 프로그래매틱 전용) → 인라인 정책:
```json
{ "Version": "2012-10-17", "Statement": [{
  "Sid": "DashboardRead", "Effect": "Allow",
  "Action": ["dynamodb:GetItem", "dynamodb:Query"],
  "Resource": ["arn:aws:dynamodb:*:*:table/slackops-agent",
               "arn:aws:dynamodb:*:*:table/slackops-agent/index/*"] }]}
```
- [ ] 승인(쓰기)까지 허용하려면 `Action` 에 `dynamodb:UpdateItem`,`dynamodb:PutItem` 추가.
- [ ] Security credentials → **Create access key**("Application outside AWS") → `AKIA…`/secret 확보(secret 은 이때만 — 안전 보관).

### D-2. Vercel 프로젝트 + 환경변수
- [ ] Vercel → New Project → repo 연결 → **Root Directory = `web`**.
- [ ] Settings → Environment Variables:
      | Key | Value |
      | --- | --- |
      | `DDB_TABLE` | `slackops-agent` |
      | `AWS_REGION` | `us-east-1` (테이블 생성 리전과 일치) |
      | `AWS_ACCESS_KEY_ID` | `AKIA...` |
      | `AWS_SECRET_ACCESS_KEY` | `...` |
      | `DASHBOARD_APPROVER` | 표시할 승인자명 |
- [ ] ⚠️ **`DDB_ENDPOINT` 는 설정하지 않는다** — 미설정 시 실 DynamoDB 로 연결(설정 시 로컬 모드).
- [ ] Deploy → **배포 URL + Team ID 기록**(제출물).

---

## [E] 실데이터 채우기 + 수치 캡처

> 결과물: 빈 대시보드 방지 + 영상·설명용 실측치(소요 N초 / 비용 $0.0X / tool call M회).

- [ ] **실데이터 생성**(택1):
      - (A 정석) Slack 에서 `/devops diagnose <service>` → worker 가 실 Claude 실행 → DynamoDB 에 Job/Audit/Metric 적재.
      - (B 대안) 실 DynamoDB 데모 시드(`scripts/seed.mjs --real` 옵션 — 필요 시 추가).
- [ ] **수치 캡처**: diagnose 1회의 span duration / `devops.run` span 의 tokens·cost / tool call 횟수.
      (선택) ADOT Collector 구성 시 CloudWatch EMF + X-Ray 로 확인(`deploy/adot/collector-config.yaml`).
- [ ] **DynamoDB 콘솔 스크린샷** — 실 Job/Audit/Metric 항목이 보이는 상태로.

---

## [F] 제출물 체크리스트 (H0 Requirements, 마감 6/29)

- [ ] **텍스트 설명** — 무엇/누구/왜 + "AWS Database used: **DynamoDB**". 보안(권한 L0/1 + 주입방어 4계층)·계측(OTel) 차별화 서술. AI 초안을 **본인 목소리로 편집(필수)**.
- [ ] **아키텍처 다이어그램** — Slack+Vercel→DynamoDB single-table→EC2 worker→Claude/도구 + OTel + 권한·주입방어 + 이벤트구동(EventBridge→Lambda). (`docs/submission/architecture.png`)
- [ ] **데모영상 <3분(YouTube)** — 문제→대상→동작(diagnose, 대시보드 승인 게이트)→DB 통합 설명. README 낭독 금지.
- [ ] **DynamoDB 사용 증빙 스크린샷** ([B-2]/[E]).
- [ ] **Published Vercel Link + Team ID** ([D-2]).
- [ ] **(보너스 +0.6)** 공개 아티클(dev.to/medium/LinkedIn) + 해커톤 목적 명시 + **#H0Hackathon**, 6/29 전 발행.

### DB 정당화 한 문장 (제출 설명·영상에 그대로)
> Slack 과 Vercel 두 control plane 이 하나의 작업 큐를 공유 → **DynamoDB conditional write** 로 별도 코디네이터 없이
> atomic job claim + optimistic-lock 승인 게이트 구현. (Aurora 아닌 DynamoDB 인 이유)

---

## [F·끝] 제출 후 — 비용 절약 (심사 6/30~7/24)

- [ ] EC2 stop: `aws ec2 stop-instances --instance-ids "$INSTANCE_ID"` (상시 가동 금지 불변).
- [ ] DynamoDB(온디맨드)·Vercel 은 유지 — idle ~$0, 대시보드 링크 살아있어야 심사 가능.
- [ ] 노출 의심·종료 시 Vercel IAM 키 Deactivate→Delete.

---

## 부록 1 — 트러블슈팅

| 증상 | 점검 |
| --- | --- |
| `/devops ping` 무응답 | `journalctl -u slackops-devops-agent` — Socket 연결/토큰 로드 실패? SSM 이름·복호화 권한. |
| 서비스 부팅 실패 | user-data `git clone` 인증(private repo, [B-3] 주의). `get-console-output` 으로 설치 단계 확인. |
| DynamoDB AccessDenied | Instance Profile(EC2) 또는 Vercel IAM 키(대시보드) 테이블/리전 일치 + 정책 statement 확인. |
| SSM 토큰 복호화 실패 | KMS 기본키 권한 + `ssm:GetParameter` + `--with-decryption`. |
| EC2 접속 불가 | 인바운드 0 이 정상 — SSH 대신 **SSM Session Manager**. |
| Vercel 빈 대시보드 | `DDB_ENDPOINT` 가 잘못 설정됐는지(미설정이어야 실 DynamoDB) + 실데이터 적재([E]) 확인. |

## 부록 2 — 비용 추정 + 정리(cleanup)

### AWS 비용 추정 (us-east-1, 2026-06 기준)
| 리소스 | 단가 | 24h | 평일 09–19(10h) |
| --- | --- | --- | --- |
| EC2 c7i.large (on-demand) | ~$0.0893/h | ~$2.14 | ~$0.89 |
| EBS 8GB gp3 (루트) | $0.08/GB·월 | ~$0.02 | ~$0.02 |
| DynamoDB 온디맨드(idle) · SSM Standard · CloudWatch(프리티어) | — | ~$0 | ~$0 |
| **합계** | | **≈ $2.16/day** | **≈ $0.9/day** |
- **Claude 추론비는 AWS 아님**(구독 토큰 귀속) → AWS 청구 미포함.
- 보유 $63.91 기준 24h 풀가동 ≈ 29일치 → 빠듯. **EventBridge 스케줄 + 캡처 직후 stop 권장**(e2e 캡처는 수십 분 → 하루 $0.2 미만 가능).
- (선택) `INSTANCE_TYPE=t3.medium`(~$1/day@24h)로 낮춰도 데모 충분.

### 정리(cleanup)

```sh
aws ec2 terminate-instances --instance-ids "$INSTANCE_ID"
aws dynamodb delete-table --table-name slackops-agent          # 온디맨드라 미삭제해도 ~0원
# IAM: instance-profile 에서 role 분리 → profile 삭제 → role-policy 삭제 → role 삭제
```

## 부록 3 — 빠른 실행 (자격증명 유효 가정)

```sh
export AWS_REGION=us-east-1
# [A] Slack App 토큰 (UI 후)
aws ssm put-parameter --name /slackops/SLACK_BOT_TOKEN         --type SecureString --value 'xoxb-...'
aws ssm put-parameter --name /slackops/SLACK_APP_TOKEN         --type SecureString --value 'xapp-...'
aws ssm put-parameter --name /slackops/CLAUDE_CODE_OAUTH_TOKEN --type SecureString --value 'sk-ant-oat...'
# [B] 인프라 (순서 고정)
( cd deploy/iam && ./create-role.sh )
( cd deploy/dynamodb && ./create-table.sh )
INSTANCE_ID="$( cd deploy/ec2 && ./launch-instance.sh )"; echo "$INSTANCE_ID"
( cd deploy/eventbridge && ./create-schedules.sh "$INSTANCE_ID" )
# [C] Slack 에서 /devops ping → pong
# [D] Vercel: 읽기전용 IAM 키 → web/ 배포(Root=web, DDB_ENDPOINT 미설정)
```
