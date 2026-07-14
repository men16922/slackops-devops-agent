# deploy/ — slackops-devops-agent
최종 갱신: 2026-06-14

> Day 1–3 인프라 산출물. **전부 ready-to-run — 실행은 유효한 AWS 자격증명(로컬 운영자)으로 수동 수행.**
> EC2는 bootstrap Instance Profile만 사용하고, 서비스는 여기서 발급한 단기 STS runtime
> role credential으로 동작한다. 장기 Access Key는 사용·저장하지 않는다.

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
   - **Claude 추론 인증 (구독 계정)**: 로컬에서 장수명 토큰 발급 후 SSM 저장.
     추론비는 구독 계정에 귀속 → AWS 크레딧과 분리. EC2 엔 `ANTHROPIC_API_KEY` 를 두지 않는다.
     ```sh
     claude setup-token   # 구독 로그인 → sk-ant-oat... 토큰 출력
     aws ssm put-parameter --name /slackops/CLAUDE_CODE_OAUTH_TOKEN --type SecureString --value 'sk-ant-oat...'
     ```
2. **IAM Role + Instance Profile**: `iam/create-role.sh`
   - **bootstrap role**은 여섯 `/slackops/` secret의 `GetParameter`와 같은 계정의
     runtime/MCP role 전환만 허용한다. S3와 runtime AWS read 권한은 없다.
   - **runtime role**은 CloudWatch/Logs/EKS/거버넌스 읽기, OTel export, `slackops-agent`
     DynamoDB control plane만 가진다. SSM secret은 읽지 못한다.
   - **internal MCP role**은 `slackops-agent` DynamoDB queue의 Get/Put/Update/Query만
     가진다. 부팅 시 1시간 STS credential으로 발급되고 45분마다 회전한다.
3. **DynamoDB 단일테이블 provision**: `dynamodb/create-table.sh`
   - **온디맨드(PAY_PER_REQUEST)** — bursty·저빈도 워크로드라 용량계획 불필요·idle 시 ~0원, GSI 도 자동 상속.
   - `slackops-agent` (PK/SK + GSI1 status 질의 + GSI2 일자 feed). Job/Audit/Telemetry 공유.
   - 멱등(이미 있으면 생략). 기본 region `us-east-1`(코드 기본값과 일치, `AWS_REGION` 으로 변경) — EC2 기동 전 선행.
4. **EC2 기동**: `ec2/launch-instance.sh`
   - c7i.large, AL2023, IMDSv2 강제, **인바운드 규칙 없는 SG**(Socket Mode 아웃바운드 전용).
   - `user-data.sh` 가 도구 체인(kubectl/terraform/gh/helm/jq/Claude Code) 설치 + systemd 서비스 **4개** 등록:
     `slackops-devops-agent`(Slack 앱), `-worker`(승인 job 실행 poller), `-chat-agent`(웹 대화형 producer 응답 poller).
     `-monitor`는 Tier1 신호 관찰 producer다. worker·chat_agent·monitor는 DynamoDB 를 outbound
     폴링만 한다(인바운드 0 유지). **이들이 없으면 웹 승인 실행·채팅 응답·자동 제안이 멈춘다.**
   - 4개 서비스는 IMDS metadata endpoint를 차단한다. root-only credential refresher timer가
     45분마다 단기 runtime/MCP credential을 회전하고 서비스를 재시작한다.
   - 4개 서비스의 direct IP egress는 차단된다. localhost Squid가 Slack·Claude·GitHub·AWS·Terraform
     도메인만 proxy하며, proxy 자신도 localhost/link-local 목적지를 거부한다.
   - `REPO_URL` 의 `CHANGE_ME` 를 실제 GitHub repo 로 교체 필요.
5. **EventBridge 스케줄**: `eventbridge/create-schedules.sh <instance-id>`
   - 기본 평일 09:00 start / 19:00 stop (Asia/Seoul). 상시 가동 금지 불변.
6. **ADOT Collector** (Day 8–9): `adot/collector-config.yaml` 로 EC2 에 collector 구성.

## 검증
- EC2 부팅 후 서비스 4개와 credential timer가 active인지 확인:
  `systemctl status slackops-devops-agent slackops-devops-agent-worker slackops-devops-agent-chat-agent slackops-devops-agent-monitor slackops-runtime-credentials-refresh.timer`.
- `systemctl status squid`가 active인지 확인하고, D17 리허설에서는 systemd sandbox에서 allowlisted
  `https://api.github.com`은 성공하고 unlisted HTTPS domain은 proxy가 거부하는지 확인한다.
- Slack 채널에서 `/devops ping` → `:white_check_mark: pong ...` 응답.
- `curl 127.0.0.1:8080/health` (EC2 내부) → `{"status":"ok"}`.
- 웹 대시보드/채팅 데모 직전: EventBridge stop 스케줄로 인스턴스가 꺼져 있으면 승인 실행·채팅 응답이 멈추므로
  `aws ec2 start-instances --instance-ids <id>` 로 **running 확인** 후 진행.
