#!/usr/bin/env bash
# EC2 user-data — Amazon Linux 2023 기준 도구 체인 설치 + systemd 서비스 등록.
# 자격증명은 Instance Profile 로 주입 — 이 스크립트에 키/토큰 하드코딩 금지.
# Slack 토큰 + Claude 구독 OAuth 토큰은 SSM Parameter Store(SecureString)에서 부팅 시 로드.
# Claude 추론은 구독 계정(CLAUDE_CODE_OAUTH_TOKEN)으로만 — ANTHROPIC_API_KEY 는 설정 금지(API 결제 경로 차단).
set -euo pipefail

# --- 기본 도구 ---
dnf install -y git jq python3.11 python3.11-pip

# --- kubectl ---
curl -fsSLo /usr/local/bin/kubectl \
  "https://dl.k8s.io/release/$(curl -fsSL https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
chmod +x /usr/local/bin/kubectl

# --- terraform ---
dnf install -y dnf-plugins-core
dnf config-manager --add-repo https://rpm.releases.hashicorp.com/AmazonLinux/hashicorp.repo
dnf install -y terraform

# --- gh (GitHub CLI) ---
dnf config-manager --add-repo https://cli.github.com/packages/rpm/gh-cli.repo
dnf install -y gh

# --- helm ---
curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

# --- Node.js + Claude Code (Headless 실행용) ---
dnf install -y nodejs20
npm install -g @anthropic-ai/claude-code

# --- uv / uvx — AWS API MCP 서버 런처(diagnose/logs 의 agentic CloudWatch 접근) ---
# claude 가 mcp_config 의 `uvx awslabs.aws-api-mcp-server@<ver>`(read-only 모드)를 띄운다.
# /usr/local/bin 에 설치(systemd PATH 에 포함). 버전은 src/app/mcp_config.py 의 pin 과 일치.
curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin sh

# --- 서비스 사용자 + 앱 배치 ---
useradd --system --create-home --shell /sbin/nologin devopsagent || true
APP_DIR=/opt/slackops-devops-agent
# 기본값 = 실 repo. private repo 면 clone 인증 필요(public 전환 또는 SSM PAT) — deploy/README §B-3 / action_item §B-3.
# 기본 브랜치(main)를 clone — main 이 작업/제출 브랜치(전체 동기화 유지). 다른 브랜치는 REPO_BRANCH 로 override.
REPO_URL="${REPO_URL:-https://github.com/men16922/slackops-devops-agent.git}"
git clone ${REPO_BRANCH:+--branch "$REPO_BRANCH"} "$REPO_URL" "$APP_DIR" || true
python3.11 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install -e "$APP_DIR"
chown -R devopsagent:devopsagent "$APP_DIR"

# AWS API MCP 서버 캐시(devopsagent 쓰기 가능) + 패키지 pre-warm(첫 호출 콜드스타트 방지).
# stdin=/dev/null → stdio 서버가 즉시 EOF 종료, timeout 으로 상한. 효과=uvx 가 패키지 캐시.
UV_CACHE_DIR=/opt/slackops-devops-agent/.uv-cache
mkdir -p "$UV_CACHE_DIR"
chown -R devopsagent:devopsagent "$UV_CACHE_DIR"
sudo -u devopsagent env UV_CACHE_DIR="$UV_CACHE_DIR" PATH=/usr/local/bin:/usr/bin:/bin \
  timeout 240 uvx awslabs.aws-api-mcp-server@1.3.45 </dev/null >/dev/null 2>&1 || true

# --- Slack 토큰: SSM SecureString → 환경 파일 (디스크 평문 최소화, root 600) ---
IMDS_TOKEN="$(curl -fsSL -X PUT http://169.254.169.254/latest/api/token \
  -H 'X-aws-ec2-metadata-token-ttl-seconds: 300')"
REGION="$(curl -fsSL -H "X-aws-ec2-metadata-token: $IMDS_TOKEN" \
  http://169.254.169.254/latest/meta-data/placement/region)"
{
  echo "SLACK_BOT_TOKEN=$(aws ssm get-parameter --region "$REGION" --name /slackops/SLACK_BOT_TOKEN --with-decryption --query Parameter.Value --output text)"
  echo "SLACK_APP_TOKEN=$(aws ssm get-parameter --region "$REGION" --name /slackops/SLACK_APP_TOKEN --with-decryption --query Parameter.Value --output text)"
  # Claude Code Headless 추론 인증 — 구독 계정 장수명 토큰(`claude setup-token` 산출물).
  echo "CLAUDE_CODE_OAUTH_TOKEN=$(aws ssm get-parameter --region "$REGION" --name /slackops/CLAUDE_CODE_OAUTH_TOKEN --with-decryption --query Parameter.Value --output text)"
  echo "AWS_REGION=$REGION"
  # botocore 는 region 을 AWS_DEFAULT_REGION 에서 읽는다(AWS_REGION 만으로는 NoRegionError) — boto3 fallback + MCP 서버용.
  echo "AWS_DEFAULT_REGION=$REGION"
  # claude→uvx(AWS API MCP) 가 PATH 에서 uvx 를 찾고 캐시를 쓸 수 있게.
  echo "PATH=/usr/local/bin:/usr/bin:/bin"
  echo "UV_CACHE_DIR=/opt/slackops-devops-agent/.uv-cache"
  # PR execution is confined to this canonical repository root. The worker
  # refuses an approved change if the root/diff/path checks no longer match.
  echo "SLACKOPS_WORKSPACE_ROOT=/opt/slackops-devops-agent"
  echo "OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317"
  echo "OTEL_SERVICE_NAME=slackops-devops-agent"
  # 제안 알림(선택) — 채널 미설정 시 notifier 는 no-op. SSM 파라미터 부재 시 빈 값(부팅 실패 방지).
  echo "SLACK_NOTIFY_CHANNEL=$(aws ssm get-parameter --region "$REGION" --name /slackops/SLACK_NOTIFY_CHANNEL --query Parameter.Value --output text 2>/dev/null || true)"
  # Slack 버튼 승인자는 user ID allowlist가 비어 있으면 전부 거부(fail closed).
  echo "SLACK_APPROVER_IDS=$(aws ssm get-parameter --region "$REGION" --name /slackops/SLACK_APPROVER_IDS --query Parameter.Value --output text 2>/dev/null || true)"
  # 대시보드 deep-link 용(예: https://<app>.vercel.app). 부재 시 링크 대신 (job <id>) 텍스트.
  echo "DASHBOARD_URL=$(aws ssm get-parameter --region "$REGION" --name /slackops/DASHBOARD_URL --query Parameter.Value --output text 2>/dev/null || true)"
} > /etc/slackops-devops-agent.env
chmod 600 /etc/slackops-devops-agent.env

# --- systemd unit: Slack Socket Mode 앱(app.main) ---
cat > /etc/systemd/system/slackops-devops-agent.service <<'UNIT'
[Unit]
Description=slackops-devops-agent (Slack Socket Mode DevOps agent)
After=network-online.target
Wants=network-online.target

[Service]
User=devopsagent
EnvironmentFile=/etc/slackops-devops-agent.env
ExecStart=/opt/slackops-devops-agent/.venv/bin/python -m app.main
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT

# --- systemd unit: 공유 큐 worker(승인된 job 실행 poller) ---
# DynamoDB 를 outbound 폴링만 한다(인바운드 0 불변 유지). DDB_ENDPOINT 미설정 → 실 DynamoDB,
# 자격증명은 Instance Profile, DDB_TABLE 은 코드 기본값 slackops-agent. 무한 루프 → Restart=always.
cat > /etc/systemd/system/slackops-devops-agent-worker.service <<'UNIT'
[Unit]
Description=slackops-devops-agent worker (승인 job 실행 poller)
After=network-online.target
Wants=network-online.target

[Service]
User=devopsagent
EnvironmentFile=/etc/slackops-devops-agent.env
WorkingDirectory=/opt/slackops-devops-agent
ExecStart=/opt/slackops-devops-agent/.venv/bin/python -m app.worker
Restart=always
RestartSec=5
# Runtime boundary for the only service that can create a PR. Source writes
# remain limited to the verified worktree; system files, home secrets and
# privilege escalation are unavailable to Claude/git/gh subprocesses.
NoNewPrivileges=true
PrivateTmp=true
ProtectHome=read-only
ProtectSystem=strict
ReadWritePaths=/opt/slackops-devops-agent
UMask=0077

[Install]
WantedBy=multi-user.target
UNIT

# --- systemd unit: 대화 버스 chat_agent(웹 대화형 producer 응답 poller) ---
# 웹 채팅(awaiting_agent)을 claim → Claude 스트리밍 응답. 부재 시 채팅이 "응답 중"에 멈춘다.
cat > /etc/systemd/system/slackops-devops-agent-chat-agent.service <<'UNIT'
[Unit]
Description=slackops-devops-agent chat-agent (대화형 producer 응답 poller)
After=network-online.target
Wants=network-online.target

[Service]
User=devopsagent
EnvironmentFile=/etc/slackops-devops-agent.env
ExecStart=/opt/slackops-devops-agent/.venv/bin/python -m app.chat_agent
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT

# --- systemd unit: agent_monitor(Tier1 상주 producer — 신호 관찰 → 자율 제안) ---
# 기본 Tier1(--real 없음 → 토큰 0). 정적 _DEMO_SIGNALS 를 5분 간격 관찰 → propose_job.
# mcp_server 의 dedupe 가드가 동일 제안 반복 적재를 막는다(스팸 방지). 실관찰은 --signals-file/--real.
cat > /etc/systemd/system/slackops-devops-agent-monitor.service <<'UNIT'
[Unit]
Description=slackops-devops-agent monitor (Tier1 resident producer)
After=network-online.target
Wants=network-online.target

[Service]
User=devopsagent
EnvironmentFile=/etc/slackops-devops-agent.env
ExecStart=/opt/slackops-devops-agent/.venv/bin/python -m app.agent_monitor --loop 300
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable --now \
  slackops-devops-agent.service \
  slackops-devops-agent-worker.service \
  slackops-devops-agent-chat-agent.service \
  slackops-devops-agent-monitor.service
