#!/usr/bin/env bash
# EC2 user-data — Amazon Linux 2023 기준 도구 체인 설치 + systemd 서비스 등록.
# 자격증명은 Instance Profile 로 주입 — 이 스크립트에 키/토큰 하드코딩 금지.
# Slack 토큰은 SSM Parameter Store(SecureString)에서 부팅 시 로드.
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

# --- 서비스 사용자 + 앱 배치 ---
useradd --system --create-home --shell /sbin/nologin devopsagent || true
APP_DIR=/opt/slackops-devops-agent
REPO_URL="${REPO_URL:-https://github.com/CHANGE_ME/slackops-devops-agent.git}"
git clone "$REPO_URL" "$APP_DIR" || true
python3.11 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install -e "$APP_DIR"
chown -R devopsagent:devopsagent "$APP_DIR"

# --- Slack 토큰: SSM SecureString → 환경 파일 (디스크 평문 최소화, root 600) ---
IMDS_TOKEN="$(curl -fsSL -X PUT http://169.254.169.254/latest/api/token \
  -H 'X-aws-ec2-metadata-token-ttl-seconds: 300')"
REGION="$(curl -fsSL -H "X-aws-ec2-metadata-token: $IMDS_TOKEN" \
  http://169.254.169.254/latest/meta-data/placement/region)"
{
  echo "SLACK_BOT_TOKEN=$(aws ssm get-parameter --region "$REGION" --name /slackops/SLACK_BOT_TOKEN --with-decryption --query Parameter.Value --output text)"
  echo "SLACK_APP_TOKEN=$(aws ssm get-parameter --region "$REGION" --name /slackops/SLACK_APP_TOKEN --with-decryption --query Parameter.Value --output text)"
  echo "AWS_REGION=$REGION"
  echo "OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317"
  echo "OTEL_SERVICE_NAME=slackops-devops-agent"
} > /etc/slackops-devops-agent.env
chmod 600 /etc/slackops-devops-agent.env

# --- systemd unit ---
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

systemctl daemon-reload
systemctl enable --now slackops-devops-agent.service
