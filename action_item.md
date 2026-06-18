# ACTION_ITEM — 수동 단계 실행 runbook

최종 갱신: 2026-06-14
대상 repo: https://github.com/men16922/slackops-devops-agent (private)

> 로컬 `[auto]` 백로그(코드+테스트)는 **전부 소진**됨 — `pytest` 229 passed, 1 skipped + ruff + mypy(strict) green.
> 남은 건 전부 **운영자 수동 단계**(AWS/Slack/GitHub/Vercel — 유효 자격증명·외부 계정 필요).
> 이 문서는 `docs/NEXT_PLAN.md` 의 `[manual]` 항목을 **실행 순서대로** 풀어 쓴 것이다.
> 권위 순서: 충돌 시 `deploy/README.md` + 각 스크립트 원문 > 이 문서.

---

## 0. 전체 흐름 한눈에

```
[A] Slack App 생성 + SSM 토큰 저장   (Slack UI + aws ssm)
        ▼
[B] AWS 인프라     IAM → DynamoDB → EC2 → EventBridge   (deploy/*.sh)
        ▼
[C] e2e 검증       /devops ping → pong
        ▼
[D] Observability  ADOT Collector + diagnose 수치 캡처
        ▼
[E] GitHub App + branch protection   (PR 게이트용)
        ▼
[F] v0 대시보드 + Vercel 배포
        ▼
[G] 제출물 (다이어그램/스크린샷/데모영상/링크/아티클)
```

의존성 요약:
- **[B] IAM → DynamoDB → EC2 순서 고정** (EC2 부팅 시 Instance Profile 로 DynamoDB·SSM 접근).
- **[A] 는 [B-EC2] 이전** 완료 필수 (부팅 시 SSM 에서 토큰 로드).
- [D]/[E]/[F]/[G] 는 [C] 이후 병렬 가능.

---

## 사전 준비 (Prerequisites)

1. **AWS 계정 + 크레딧** — 해커톤 크레딧 신청/적용 완료. 청구 알림 설정 권장.
2. **로컬 AWS 자격증명** — `aws sts get-caller-identity` 로 확인. (현재 STATUS: 로컬 자격증명 무효 → 갱신 필요)
   ```sh
   aws sts get-caller-identity     # Account/Arn 출력되면 OK
   aws configure                   # 또는 SSO: aws sso login
   ```
3. **리전 고정** — 본 문서는 `ap-northeast-2`(서울) 기준. 다른 리전이면 아래 모든 명령에 `--region` 또는 `export AWS_REGION=...` 적용.
   ```sh
   export AWS_REGION=ap-northeast-2
   ```
4. **로컬 도구** — `aws` CLI v2, `git`, (대시보드용) `node`/`npm`, Vercel 계정.

---

## [A] Slack App 생성 + 토큰 저장

> 결과물: `SLACK_BOT_TOKEN`(xoxb-…), `SLACK_APP_TOKEN`(xapp-…) → SSM SecureString 저장.
> Socket Mode 이므로 **인바운드 URL 불필요**(공개 엔드포인트 없음 = 본 프로젝트 보안 불변).

### A-1. Slack App 만들기 (https://api.slack.com/apps)
1. **Create New App → From scratch** → 이름 `slackops-devops-agent`, 워크스페이스 선택.
2. **Socket Mode** (좌측 메뉴) → **Enable Socket Mode** 토글 ON.
   - 이때 **App-Level Token** 생성 프롬프트 → scope `connections:write` → 생성된 `xapp-…` 가 **`SLACK_APP_TOKEN`**.
3. **OAuth & Permissions** → **Bot Token Scopes** 추가:
   - `commands` (슬래시 명령)
   - `chat:write` (응답 게시)
   - `chat:write.public` (미초대 채널 게시, 선택)
4. **Slash Commands** → **Create New Command**:
   - Command: `/devops`
   - Short Description: `SlackOps DevOps agent`
   - Usage Hint: `ping | logs <svc> | diagnose <svc> | tf-review | pr <설명>`
   - (Socket Mode 라 Request URL 칸은 비워도 됨)
5. **Install App** (좌측) → **Install to Workspace** → 승인.
   - 설치 후 **Bot User OAuth Token** `xoxb-…` 가 **`SLACK_BOT_TOKEN`**.

### A-2. 토큰을 SSM SecureString 으로 저장
> 토큰은 **절대 repo/.env 에 커밋 금지**. SSM SecureString 이 source of truth, EC2 가 부팅 시 복호화 로드.

```sh
aws ssm put-parameter --name /slackops/SLACK_BOT_TOKEN --type SecureString --value 'xoxb-...'
aws ssm put-parameter --name /slackops/SLACK_APP_TOKEN --type SecureString --value 'xapp-...'
```

검증:
```sh
aws ssm get-parameter --name /slackops/SLACK_BOT_TOKEN --with-decryption \
  --query Parameter.Value --output text | head -c 8   # "xoxb-..." 앞부분만
```

---

## [B] AWS 인프라 (IAM → DynamoDB → EC2 → EventBridge)

> 모든 스크립트는 `deploy/` 안에서 실행. **순서 고정.**

### B-1. IAM Role + Instance Profile — `deploy/iam/create-role.sh`
읽기 전용(CloudWatch/Logs/EKS Describe/SSM Read/S3 Read) + OTel export + **DynamoDB(테이블 스코프 GetItem/PutItem/UpdateItem/Query)**.
Access Key 발급 금지 — Instance Profile 만.

```sh
cd deploy/iam
./create-role.sh
# → OK: role=slackops-devops-agent-role profile=slackops-devops-agent-profile
```

검증:
```sh
aws iam get-instance-profile --instance-profile-name slackops-devops-agent-profile \
  --query 'InstanceProfile.Roles[0].RoleName' --output text
```

> 멱등 아님: 이미 있으면 `EntityAlreadyExists` 에러. 재실행하려면 기존 role/profile 삭제 후 진행(부록 정리 참고).

### B-2. DynamoDB 단일테이블 provision — `deploy/dynamodb/create-table.sh`
**온디맨드(PAY_PER_REQUEST)** — bursty·저빈도 워크로드라 용량계획 불필요·idle 시 ~0원, GSI 자동 상속.
`slackops-agent` (PK/SK + GSI1 status 질의 + GSI2 일자 feed). Job/Audit/Telemetry 공유. **멱등**(있으면 생략).

```sh
cd ../dynamodb        # deploy/dynamodb
AWS_REGION=ap-northeast-2 ./create-table.sh
# → OK: table 'slackops-agent' created (PAY_PER_REQUEST, GSI1+GSI2) in ap-northeast-2
```

검증:
```sh
aws dynamodb describe-table --table-name slackops-agent \
  --query 'Table.{Status:TableStatus,Billing:BillingModeSummary.BillingMode,GSIs:length(GlobalSecondaryIndexes)}'
# → Status=ACTIVE, Billing=PAY_PER_REQUEST, GSIs=2
```

### B-3. EC2 기동 — `deploy/ec2/launch-instance.sh`
c7i.large, 최신 AL2023, IMDSv2 강제, **인바운드 규칙 없는 SG**(Socket Mode 아웃바운드 전용).
`user-data.sh` 가 도구체인(kubectl/terraform/gh/helm/jq/Node/Claude Code) 설치 + systemd 등록.

**먼저 `user-data.sh` 의 `REPO_URL` 을 실제 repo 로 교체:**
```sh
cd ../ec2             # deploy/ec2
# REPO_URL 기본값 CHANGE_ME → 실제 repo 로. private repo 면 clone 인증 필요(아래 주의).
sed -i '' 's#https://github.com/CHANGE_ME/slackops-devops-agent.git#https://github.com/men16922/slackops-devops-agent.git#' user-data.sh
```

> ⚠️ **private repo clone 주의:** user-data 의 `git clone` 은 인증이 없다. 옵션:
> - (간단) 데모용으로 repo 를 **public 전환** 후 부팅, 또는
> - SSM 에 GitHub PAT 저장 → user-data 에서 `https://<token>@github.com/...` 로 clone, 또는
> - EC2 에 deploy key(SSH) 구성.
> 데모 목적이면 public 전환이 가장 단순.

기동:
```sh
INSTANCE_ID="$(./launch-instance.sh)"
echo "$INSTANCE_ID"        # i-xxxxxxxx
```

부팅·설치 진행 확인(user-data 는 수 분 소요):
```sh
aws ec2 wait instance-running --instance-ids "$INSTANCE_ID"
# 콘솔 로그로 user-data 진행 확인 (부팅 후 1~2분 뒤부터)
aws ec2 get-console-output --instance-id "$INSTANCE_ID" --query Output --output text | tail -40
```

### B-4. EventBridge 스케줄 — `deploy/eventbridge/create-schedules.sh`
EC2 stop/start 스케줄(상시 가동 금지 불변). 기본 평일 09:00 start / 19:00 stop (Asia/Seoul).

```sh
cd ../eventbridge     # deploy/eventbridge
./create-schedules.sh "$INSTANCE_ID"
# → OK: schedules created for i-xxxx (Asia/Seoul)
```

> 데모 직전엔 스케줄과 무관하게 인스턴스가 running 인지 확인. 필요 시 수동 start:
> `aws ec2 start-instances --instance-ids "$INSTANCE_ID"`

---

## [C] e2e 검증 — `/devops ping`

> 결과물: Slack → EC2 → pong 왕복 1회 성공. (코드의 마지막 미검증 경로)

1. **서비스 상태**(SSM Session Manager 또는 콘솔로 EC2 접속):
   ```sh
   systemctl status slackops-devops-agent      # active (running)
   journalctl -u slackops-devops-agent -n 50    # 부팅 로그/Socket 연결 확인
   curl 127.0.0.1:8080/health                   # {"status":"ok"}
   ```
   - 접속은 SSH 대신 **SSM Session Manager** 권장(인바운드 포트 0 유지): `aws ssm start-session --target "$INSTANCE_ID"`
     (SSM Agent 는 AL2023 기본 탑재, IAM 에 SSM 권한 필요 시 `AmazonSSMManagedInstanceCore` 부착 검토)
2. **Slack 에서**: 앱을 채널에 초대(`/invite @slackops-devops-agent`) 후
   ```
   /devops ping
   ```
   → `:white_check_mark: pong ...` 응답이면 e2e 성공. **스크린샷 캡처**(제출물 [G]).
3. 실패 시 트러블슈팅 → 부록 참고.

---

## [D] Observability — ADOT Collector + 수치 캡처

> 결과물: diagnose 1회의 실측치(소요 N초 / 비용 $0.0X / tool call M회) 캡처.

1. **ADOT Collector 구성** (`deploy/adot/collector-config.yaml`): OTLP(127.0.0.1:4317/4318) 수신 → CloudWatch EMF(`SlackOpsDevOpsAgent` 네임스페이스) + X-Ray.
   - EC2 에 ADOT collector 설치 후 위 config 로 기동(서비스/컨테이너 택1). 앱은 이미 `OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317` 로 export.
2. **수치 캡처**:
   ```
   /devops diagnose <service>
   ```
   - CloudWatch Logs `/slackops-devops-agent/metrics` (EMF) + X-Ray 트레이스에서 run span 확인.
   - 캡처 항목: 실행 시간(span duration), tokens/cost(`devops.run` span 속성), tool call 횟수.

---

## [E] GitHub App + branch protection

> 결과물: PR 게이트 안전성 — 자동 머지 차단, 최소 스코프 토큰.

1. **GitHub App(또는 fine-grained PAT) 최소 스코프**: `contents:write`(브랜치/커밋), `pull_requests:write`(PR 생성). 그 이상 금지.
   - EC2 의 `gh`/`git` 가 이 자격으로만 push/PR. 토큰은 SSM SecureString 권장.
2. **Branch protection**(repo Settings → Branches → `main`):
   - Require a pull request before merging ✅
   - Require approvals (≥1) ✅  → **사람 승인 없이는 머지 불가**(출력 게이트 3계층의 마지막).
   - Do not allow bypassing the above settings ✅
   - (선택) Require status checks to pass.

---

## [F] v0 대시보드 + Vercel 배포

> 결과물: DynamoDB 의 Job/Audit/Telemetry 피드를 보여주는 Next.js 대시보드 + Vercel 공개 링크.

1. **v0 로 스캐폴드** (https://v0.dev): `web/` 에 Next.js(App Router) 대시보드 생성.
   - 화면: 최근 Job 피드(상태/명령/시각), Audit 타임라인, Telemetry(토큰/비용/소요).
2. **server actions ↔ DynamoDB** (읽기 전용):
   - GSI2(`FEED`/`AUDIT#yyyymmdd`/`METRIC#yyyymmdd`) Query 로 피드 조회. 키 구조는 `src/app/store/*.py` 주석 참고.
   - 대시보드 자격증명은 **읽기 전용 IAM**(GetItem/Query, 테이블 스코프) — 별도 사용자/역할.
3. **Vercel 배포**: 프로젝트 연결 → 환경변수(AWS 자격/리전/테이블명) 설정 → deploy.
   - **Team ID** 와 **배포 URL** 기록(제출물 [G]).

---

## [G] 제출물 체크리스트

- [ ] **아키텍처 다이어그램** — `docs/images/architecture.png` (이미 repo 에 있음, 최신화 확인)
- [ ] **DynamoDB 스크린샷** — 테이블 + 실 항목(Job/Audit/Metric) 콘솔 캡처
- [ ] **3분 데모 영상** — `/devops ping` → `diagnose` → (가능 시)`tf-review`/`pr` 흐름 + 대시보드
- [ ] **텍스트 설명** — 보안(권한 L0/1 + 주입 방어 4계층) + 계측(OTel) 차별화 축 서술
- [ ] **Vercel 링크 + Team ID**
- [ ] **(보너스) 아티클** — LOOP 엔지니어링/안전한 에이전트 운영 레퍼런스 (`docs/LOOP_ENGINEERING.md` 기반)

---

## 부록 1 — 트러블슈팅

| 증상 | 점검 |
| --- | --- |
| `/devops ping` 무응답 | `journalctl -u slackops-devops-agent` — Socket 연결/토큰 로드 실패? SSM 파라미터 이름·복호화 권한 확인. |
| 서비스 부팅 실패 | user-data 의 `git clone` 인증(private repo) — [B-3] 주의 참고. `get-console-output` 으로 설치 단계 확인. |
| DynamoDB AccessDenied | Instance Profile 에 `DynamoDbControlPlane` statement 적용됐는지(`create-role.sh` 재실행 필요할 수 있음), 테이블명/리전 일치. |
| SSM 토큰 복호화 실패 | KMS 기본키 권한 + `ssm:GetParameter` + `--with-decryption`. |
| EC2 접속 불가 | 인바운드 0 이 정상 — SSH 대신 **SSM Session Manager** 사용. |

## 부록 2 — 비용 / 정리(cleanup)

- **상시 가동 금지**: EventBridge 스케줄로 평일만 가동. 데모 후 수동 stop:
  `aws ec2 stop-instances --instance-ids "$INSTANCE_ID"`
- **DynamoDB 온디맨드**: idle 시 거의 0원 — 삭제 불필요하나 종료 시:
  `aws dynamodb delete-table --table-name slackops-agent`
- **EC2 종료**: `aws ec2 terminate-instances --instance-ids "$INSTANCE_ID"`
- **IAM 정리**: instance-profile 에서 role 분리 → profile 삭제 → role-policy 삭제 → role 삭제.

## 부록 3 — 빠른 실행 순서 (자격증명 유효 가정)

```sh
export AWS_REGION=ap-northeast-2
# [A] Slack App 토큰 저장 (UI 후)
aws ssm put-parameter --name /slackops/SLACK_BOT_TOKEN --type SecureString --value 'xoxb-...'
aws ssm put-parameter --name /slackops/SLACK_APP_TOKEN --type SecureString --value 'xapp-...'
# [B] 인프라
( cd deploy/iam && ./create-role.sh )
( cd deploy/dynamodb && ./create-table.sh )
( cd deploy/ec2 && sed -i '' 's#CHANGE_ME#men16922#' user-data.sh && INSTANCE_ID="$(./launch-instance.sh)"; echo "$INSTANCE_ID" )
( cd deploy/eventbridge && ./create-schedules.sh "$INSTANCE_ID" )
# [C] Slack 에서 /devops ping → pong 확인
```
