# deploy/ — slackops-devops-agent
최종 갱신: 2026-06-11

> Day 1–3 인프라 산출물. **전부 ready-to-run — 실행은 유효한 AWS 자격증명(로컬 운영자)으로 수동 수행.**
> 에이전트 런타임은 IAM Instance Profile 만 사용(Access Key 금지).

## 실행 순서
1. **Slack App 생성 (수동, Slack UI)**
   - https://api.slack.com/apps → Create New App → Socket Mode 활성화.
   - App-Level Token(`connections:write`) = `SLACK_APP_TOKEN`, Bot Token = `SLACK_BOT_TOKEN`.
   - Slash command `/devops` 등록(Socket Mode 라 Request URL 불필요).
   - 토큰을 SSM SecureString 으로 저장:
     ```sh
     aws ssm put-parameter --name /slackops/SLACK_BOT_TOKEN --type SecureString --value 'xoxb-...'
     aws ssm put-parameter --name /slackops/SLACK_APP_TOKEN --type SecureString --value 'xapp-...'
     ```
2. **IAM Role + Instance Profile**: `iam/create-role.sh`
   - 읽기 전용 기준(CloudWatch/Logs/EKS Describe/SSM Read/S3 Read)
     + OTel export 최소 쓰기(PutMetricData/PutLogEvents/X-Ray) — 계측 파이프라인용 예외, 그 외 쓰기 없음.
3. **EC2 기동**: `ec2/launch-instance.sh`
   - c7i.large, AL2023, IMDSv2 강제, **인바운드 규칙 없는 SG**(Socket Mode 아웃바운드 전용).
   - `user-data.sh` 가 도구 체인(kubectl/terraform/gh/helm/jq/Claude Code) 설치 + systemd 서비스 등록.
   - `REPO_URL` 의 `CHANGE_ME` 를 실제 GitHub repo 로 교체 필요.
4. **EventBridge 스케줄**: `eventbridge/create-schedules.sh <instance-id>`
   - 기본 평일 09:00 start / 19:00 stop (Asia/Seoul). 상시 가동 금지 불변.
5. **ADOT Collector** (Day 8–9): `adot/collector-config.yaml` 로 EC2 에 collector 구성.

## 검증
- EC2 부팅 후: `systemctl status slackops-devops-agent` → active.
- Slack 채널에서 `/devops ping` → `:white_check_mark: pong ...` 응답.
- `curl 127.0.0.1:8080/health` (EC2 내부) → `{"status":"ok"}`.
