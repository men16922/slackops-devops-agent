# SLACK_GUIDE — Slack DevOps 에이전트 운영 가이드

> **대상:** 에이전트 백엔드(EC2)를 **배포·운영하는 사람**. 웹 대시보드는 [DASHBOARD_GUIDE.md](DASHBOARD_GUIDE.md),
> 직접 검증 미결 항목은 [QA_TEST.md](QA_TEST.md), AWS 인프라 실행 순서·현재 상태는 `docs/runbooks/deploy-checklist.md`(권위).

---

## 0. 무엇 / 보안 원칙 (먼저 읽기)
Slack 자연어 명령 → EC2의 Claude Code Headless 가 안전 게이트를 거쳐 AWS/K8s/Terraform/GitHub 컨텍스트로 분석·자동화. MVP = **Read-Only 분석 + PR 생성**.

- **EC2 런타임은 AWS Access Key 를 절대 쓰지 않는다** — IAM Instance Profile 만(`deploy/ec2/user-data.sh`).
- **Socket Mode 전용** — 인바운드 포트 0(공개 엔드포인트 없음). 에이전트는 아웃바운드 폴링만.
- **토큰/키는 **코드·git 커밋 금지** — 운영 토큰은 SSM SecureString 이 source of truth.
- **권한 게이트** — Level 0(관찰)/1(준비·PR) 만 활성. L2(실행)·prod·IAM·DB 변경은 **금지 불변**.
- **주입 방어 4계층** — Sanitizer(untrusted 격리) / Tool Allowlist / 출력 게이트(diff 사람 승인) / Template Prompt.

---

## 1. Slack 명령어 (MVP)
앱을 채널에 초대(`/invite @slackops-devops-agent`) 후:

| 명령 | 동작 | 권한 |
| --- | --- | --- |
| `/devops ping` | 헬스 체크 → `pong` | L0 |
| `/devops logs <service>` | CloudWatch 조회 + 분석 (AWS API MCP) | L0 |
| `/devops diagnose <service>` | CloudWatch + kubectl + git diff 종합 진단 | L0 |
| `/devops tf-review` | terraform plan 리스크/비용/보안 리뷰 (apply 경로 없음) | L1 |
| `/devops pr <설명>` | 브랜치→수정→테스트→PR (**diff 사람 승인 게이트**) | L1 |

> L0(diagnose/logs)는 즉시 실행. L1(pr)은 diff 를 먼저 Slack 에 올리고 **사람 승인 후에만** push/PR.

---

## 2. 시크릿 — 무엇을 어디에
| 시크릿 | 용도 | 저장 위치 | 발급 |
| --- | --- | --- | --- |
| `SLACK_BOT_TOKEN` (`xoxb-…`) | Slack Bot | **SSM** `/slackops/SLACK_BOT_TOKEN` | Slack App → OAuth |
| `SLACK_APP_TOKEN` (`xapp-…`) | Socket Mode | **SSM** `/slackops/SLACK_APP_TOKEN` | Slack App → App-Level Token |
| `CLAUDE_CODE_OAUTH_TOKEN` (`sk-ant-oat…`) | Claude 추론(구독) | **SSM** `/slackops/CLAUDE_CODE_OAUTH_TOKEN` | `claude setup-token` |
| AWS 자격증명 (EC2 런타임) | AWS/DynamoDB 접근 | **없음** — IAM Instance Profile | `deploy/iam/create-role.sh` |

### 2.1 Slack 토큰 (SSM)
Slack App(Socket Mode) 생성 후:
```sh
aws ssm put-parameter --name /slackops/SLACK_BOT_TOKEN --type SecureString --value 'xoxb-...'
aws ssm put-parameter --name /slackops/SLACK_APP_TOKEN --type SecureString --value 'xapp-...'
```
EC2 부팅 시 `user-data.sh` 가 `/etc/slackops-devops-agent.env`(root 600) 로 자동 로드.

### 2.2 Claude 구독 토큰 (SSM)
추론비를 **구독 계정**에 귀속(AWS 크레딧과 분리). EC2 엔 `ANTHROPIC_API_KEY` 를 두지 않는다(API 결제 경로 차단).
```sh
claude setup-token                                  # 구독 로그인 → sk-ant-oat... 출력
aws ssm put-parameter --name /slackops/CLAUDE_CODE_OAUTH_TOKEN --type SecureString --value 'sk-ant-oat...'
```
- 만료/인증 실패 시: 재발급 → SSM 갱신 → `sudo systemctl restart slackops-devops-agent`.

---

## 3. 배포 순서 (요약)
실행 순서·현재 상태·검증 체크박스는 **`docs/runbooks/deploy-checklist.md`(권위)** 참조. 요약:

1. Slack App 생성 + SSM 토큰(§2.1·§2.2)
2. `deploy/iam/create-role.sh` — IAM Role + Instance Profile (**순서 고정**: 부팅 시 Profile 로 DynamoDB·SSM 접근)
3. `deploy/dynamodb/create-table.sh` — DynamoDB 단일테이블(온디맨드)
4. `deploy/ec2/launch-instance.sh` — EC2 기동 (user-data 가 도구체인 + systemd 3개 등록: slack 앱·worker·chat-agent)
5. `deploy/eventbridge/create-schedules.sh <instance-id>` — stop/start 스케줄(상시 가동 금지 불변)
6. `/devops ping` → `pong` e2e 확인

> ⚠️ private repo clone: user-data 의 `git clone` 은 무인증 → 데모용 **public 전환**(가장 단순) · SSM PAT · deploy key 중 택1.

---

## 4. e2e 검증 — `/devops ping`
접속은 SSH 대신 **SSM Session Manager**(인바운드 0 유지): `aws ssm start-session --target "$INSTANCE_ID"`.
```sh
systemctl status slackops-devops-agent slackops-devops-agent-worker slackops-devops-agent-chat-agent  # 3개 active
curl 127.0.0.1:8080/health        # {"status":"ok"}
```
Slack 에서 `/devops ping` → `:white_check_mark: pong … on ip-…ec2.internal` 이면 클라우드 왕복 성공.

| 증상 | 점검 |
| --- | --- |
| `/devops ping` 무응답 | `journalctl -u slackops-devops-agent -n 50` — Socket 연결/토큰 로드 실패? SSM 이름·복호화 권한. |
| 서비스 부팅 실패 | user-data `git clone` 인증(private repo) — `get-console-output` 으로 설치 단계 확인. |
| DynamoDB AccessDenied | Instance Profile 정책 + 테이블명/리전 일치. |
| SSM 토큰 복호화 실패 | KMS 기본키 권한 + `ssm:GetParameter` + `--with-decryption`. |
| EC2 접속 불가 | 인바운드 0 이 정상 — SSH 대신 SSM Session Manager. |

---

## 5. 비용 절약 / 정리
상시 가동 금지 불변. 데모/캡처 직후 stop 권장(c7i.large 24h ≈ $2.16, 평일 10h ≈ $0.9 — `deploy-checklist.md` 부록 2).
```sh
aws ec2 stop-instances      --instance-ids "$INSTANCE_ID"   # 심사기간엔 stop, 필요 시 start
aws ec2 terminate-instances --instance-ids "$INSTANCE_ID"   # 완전 종료
aws dynamodb delete-table   --table-name slackops-agent     # 온디맨드라 미삭제해도 ~0원
```
- Claude 추론비는 AWS 아님(구독 토큰 귀속) → AWS 청구 미포함.
- 심사기간(제출 후)엔 EC2 stop, DynamoDB·Vercel 은 유지(idle ~$0, 대시보드 링크 살아있어야 심사 가능).
