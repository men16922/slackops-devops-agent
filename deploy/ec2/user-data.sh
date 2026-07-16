#!/usr/bin/env bash
# EC2 user-data — Amazon Linux 2023 기준 도구 체인 설치 + systemd 서비스 등록.
# 자격증명은 Instance Profile 로 주입 — 이 스크립트에 키/토큰 하드코딩 금지.
# Slack 토큰 + Claude 구독 OAuth 토큰은 SSM Parameter Store(SecureString)에서 부팅 시 로드.
# Claude 추론은 구독 계정(CLAUDE_CODE_OAUTH_TOKEN)으로만 — ANTHROPIC_API_KEY 는 설정 금지(API 결제 경로 차단).
set -euo pipefail

# --- 기본 도구 ---
dnf install -y git jq python3.11 python3.11-pip squid

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
# 기본값 = 실 repo. private repo 면 clone 인증 필요(public 전환 또는 SSM PAT) — deploy/README §B-3 / action_item §B-3.
# 기본 브랜치(main)를 clone — main 이 작업/제출 브랜치(전체 동기화 유지). 다른 브랜치는 REPO_BRANCH 로 override.
REPO_URL="${REPO_URL:-https://github.com/men16922/slackops-devops-agent.git}"
SOURCE_ARCHIVE_URL=""
SOURCE_ARCHIVE_SHA256=""
if [[ -n "$SOURCE_ARCHIVE_URL" ]]; then
  [[ -n "$SOURCE_ARCHIVE_SHA256" ]] || {
    echo "SOURCE_ARCHIVE_SHA256 is required when SOURCE_ARCHIVE_URL is set" >&2
    exit 1
  }
  install -d -m 755 "$APP_DIR"
  curl --fail --location --proto '=https' --tlsv1.2 "$SOURCE_ARCHIVE_URL" \
    --output /tmp/slackops-source.tar.gz
  printf '%s  %s\n' "$SOURCE_ARCHIVE_SHA256" /tmp/slackops-source.tar.gz | sha256sum --check --status
  tar --extract --gzip --file /tmp/slackops-source.tar.gz --directory "$APP_DIR"
  rm -f /tmp/slackops-source.tar.gz
else
  git clone ${REPO_BRANCH:+--branch "$REPO_BRANCH"} "$REPO_URL" "$APP_DIR"
fi
python3.11 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install -e "$APP_DIR"
chown -R devopsagent:devopsagent "$APP_DIR"

# --- allowlist egress proxy ---
# Agent systemd units deny every non-loopback IP. Squid alone may leave the host and
# accepts only localhost callers whose CONNECT host matches this reviewed list.
install -o root -g squid -m 640 "$APP_DIR/deploy/ec2/egress-proxy.conf" /etc/squid/squid.conf
/usr/sbin/squid -k parse
systemctl enable --now squid

# --- Slack 토큰: SSM SecureString → 환경 파일 (디스크 평문 최소화, root 600) ---
IMDS_TOKEN="$(curl -fsSL -X PUT http://169.254.169.254/latest/api/token \
  -H 'X-aws-ec2-metadata-token-ttl-seconds: 300')"
REGION="$(curl -fsSL -H "X-aws-ec2-metadata-token: $IMDS_TOKEN" \
  http://169.254.169.254/latest/meta-data/placement/region)"
ACCOUNT_ID="$(aws sts get-caller-identity --region "$REGION" --query Account --output text)"
{
  echo "SLACK_BOT_TOKEN=$(aws ssm get-parameter --region "$REGION" --name /slackops/SLACK_BOT_TOKEN --with-decryption --query Parameter.Value --output text)"
  echo "SLACK_APP_TOKEN=$(aws ssm get-parameter --region "$REGION" --name /slackops/SLACK_APP_TOKEN --with-decryption --query Parameter.Value --output text)"
  # Claude Code Headless 추론 인증 — 구독 계정 장수명 토큰(`claude setup-token` 산출물).
  echo "CLAUDE_CODE_OAUTH_TOKEN=$(aws ssm get-parameter --region "$REGION" --name /slackops/CLAUDE_CODE_OAUTH_TOKEN --with-decryption --query Parameter.Value --output text)"
  echo "AWS_REGION=$REGION"
  # botocore 는 region 을 AWS_DEFAULT_REGION 에서 읽는다(AWS_REGION 만으로는 NoRegionError) — boto3 fallback + MCP 서버용.
  echo "AWS_DEFAULT_REGION=$REGION"
  # P2 deterministic scope boundary. These values are written by root at boot;
  # Slack/model input cannot select a different account, region, log group, or
  # workspace. Operators may narrow the reviewed log-group prefixes further.
  echo "AWS_ACCOUNT_ID=$ACCOUNT_ID"
  echo "SLACKOPS_POLICY_ENFORCEMENT=true"
  echo "SLACKOPS_ALLOWED_AWS_ACCOUNT_IDS=$ACCOUNT_ID"
  echo "SLACKOPS_ALLOWED_AWS_REGIONS=$REGION"
  echo "SLACKOPS_ALLOWED_LOG_GROUP_PREFIXES=/aws/"
  echo "SLACKOPS_POLICY_WORKSPACE_ROOT=$APP_DIR"
  echo "PATH=/usr/local/bin:/usr/bin:/bin"
  # Agent service egress is forced through the localhost Squid allowlist. Keep IMDS
  # outside NO_PROXY; systemd also blocks service access to it at IP level.
  echo "HTTP_PROXY=http://127.0.0.1:3128"
  echo "HTTPS_PROXY=http://127.0.0.1:3128"
  echo "ALL_PROXY=http://127.0.0.1:3128"
  echo "NO_PROXY=127.0.0.1,localhost,::1,169.254.169.254"
  echo "http_proxy=http://127.0.0.1:3128"
  echo "https_proxy=http://127.0.0.1:3128"
  echo "all_proxy=http://127.0.0.1:3128"
  echo "no_proxy=127.0.0.1,localhost,::1,169.254.169.254"
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
  # 승인 후 발급되는 단기 write credential(GitHub App). 상시 PAT 를 두지 않는다 —
  # 승인된 plan hash 재검증 직후에만 저장소/권한이 고정된 installation token 을 발급하고
  # 그 단계가 끝나면 회수한다. 넷 다 있어야 유효하며, 전부 비면 write 자격 없이 동작한다
  # (push 실패 = fail closed). 발급 자체는 앱이 하므로 자식 프로세스는 App key 를 못 본다.
  echo "SLACKOPS_PR_REPOSITORY=$(aws ssm get-parameter --region "$REGION" --name /slackops/PR_REPOSITORY --query Parameter.Value --output text 2>/dev/null || true)"
  echo "SLACKOPS_GITHUB_APP_ID=$(aws ssm get-parameter --region "$REGION" --name /slackops/GITHUB_APP_ID --query Parameter.Value --output text 2>/dev/null || true)"
  echo "SLACKOPS_GITHUB_INSTALLATION_ID=$(aws ssm get-parameter --region "$REGION" --name /slackops/GITHUB_INSTALLATION_ID --query Parameter.Value --output text 2>/dev/null || true)"
  # PEM 은 여러 줄이라 systemd EnvironmentFile 이 파싱하지 못한다 — SSM 에 base64 로 넣고
  # 앱이 디코드한다(`base64 -w0 < app.private-key.pem` 으로 저장).
  echo "SLACKOPS_GITHUB_APP_PRIVATE_KEY_B64=$(aws ssm get-parameter --region "$REGION" --name /slackops/GITHUB_APP_PRIVATE_KEY_B64 --with-decryption --query Parameter.Value --output text 2>/dev/null || true)"
} > /etc/slackops-devops-agent.env
chmod 600 /etc/slackops-devops-agent.env

# --- 단기 runtime credential: bootstrap role → runtime/MCP 전용 role ---
# 서비스와 Claude 자식 프로세스는 IMDS를 직접 읽지 않는다. root refresher만 bootstrap
# credential으로 두 target role을 assume하고, root-only 환경 파일에 단기 값을 기록한다.
install -m 700 "$APP_DIR/deploy/ec2/refresh-runtime-credentials.sh" \
  /usr/local/sbin/slackops-refresh-runtime-credentials
install -m 700 "$APP_DIR/deploy/ec2/audit-exporter.sh" \
  /usr/local/sbin/slackops-security-audit-exporter
# Required before the sandboxed exporter starts: ProtectSystem=strict exposes
# only explicitly listed writable paths, which must already exist at spawn.
install -d -o root -g root -m 700 /var/lib/slackops-security-audit
/usr/local/sbin/slackops-refresh-runtime-credentials --force
/usr/local/sbin/slackops-security-audit-exporter credential_refresh

# --- systemd unit: Slack Socket Mode 앱(app.main) ---
cat > /etc/systemd/system/slackops-devops-agent.service <<'UNIT'
[Unit]
Description=slackops-devops-agent (Slack Socket Mode DevOps agent)
After=network-online.target
Wants=network-online.target

[Service]
User=devopsagent
EnvironmentFile=/etc/slackops-devops-agent.env
EnvironmentFile=/etc/slackops-devops-agent.runtime.env
ExecStartPre=+/usr/local/sbin/slackops-refresh-runtime-credentials
ExecStart=/opt/slackops-devops-agent/.venv/bin/python -m app.main
Restart=on-failure
RestartSec=5
# The Slack process can launch Claude/MCP for Assistant turns. Give it the
# same host boundary as the worker; child processes also receive a scrubbed
# environment in app.claude_runner.
NoNewPrivileges=true
PrivateTmp=true
ProtectHome=read-only
ProtectSystem=strict
ReadWritePaths=/opt/slackops-devops-agent
UMask=0077
PrivateDevices=true
ProtectClock=true
ProtectControlGroups=true
ProtectHostname=true
ProtectKernelModules=true
ProtectKernelTunables=true
RestrictSUIDSGID=true
LockPersonality=true
ProtectProc=invisible
ProcSubset=pid
IPAddressDeny=169.254.169.254/32
IPAddressDeny=any
IPAddressAllow=127.0.0.1
IPAddressAllow=::1

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
EnvironmentFile=/etc/slackops-devops-agent.runtime.env
WorkingDirectory=/opt/slackops-devops-agent
ExecStartPre=+/usr/local/sbin/slackops-refresh-runtime-credentials
ExecStart=/opt/slackops-devops-agent/.venv/bin/python -m app.worker
Restart=always
RestartSec=5
# Runtime boundary for every service that can launch Claude/MCP. Source writes
# remain limited to the verified worktree; system files, home secrets and
# privilege escalation are unavailable to Claude/git/gh subprocesses.
NoNewPrivileges=true
PrivateTmp=true
ProtectHome=read-only
ProtectSystem=strict
ReadWritePaths=/opt/slackops-devops-agent
UMask=0077
PrivateDevices=true
ProtectClock=true
ProtectControlGroups=true
ProtectHostname=true
ProtectKernelModules=true
ProtectKernelTunables=true
RestrictSUIDSGID=true
LockPersonality=true
ProtectProc=invisible
ProcSubset=pid
IPAddressDeny=169.254.169.254/32
IPAddressDeny=any
IPAddressAllow=127.0.0.1
IPAddressAllow=::1

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
EnvironmentFile=/etc/slackops-devops-agent.runtime.env
ExecStartPre=+/usr/local/sbin/slackops-refresh-runtime-credentials
ExecStart=/opt/slackops-devops-agent/.venv/bin/python -m app.chat_agent
Restart=always
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true
ProtectHome=read-only
ProtectSystem=strict
ReadWritePaths=/opt/slackops-devops-agent
UMask=0077
PrivateDevices=true
ProtectClock=true
ProtectControlGroups=true
ProtectHostname=true
ProtectKernelModules=true
ProtectKernelTunables=true
RestrictSUIDSGID=true
LockPersonality=true
ProtectProc=invisible
ProcSubset=pid
IPAddressDeny=169.254.169.254/32
IPAddressDeny=any
IPAddressAllow=127.0.0.1
IPAddressAllow=::1

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
EnvironmentFile=/etc/slackops-devops-agent.runtime.env
ExecStartPre=+/usr/local/sbin/slackops-refresh-runtime-credentials
ExecStart=/opt/slackops-devops-agent/.venv/bin/python -m app.agent_monitor --loop 300
Restart=always
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true
ProtectHome=read-only
ProtectSystem=strict
ReadWritePaths=/opt/slackops-devops-agent
UMask=0077
PrivateDevices=true
ProtectClock=true
ProtectControlGroups=true
ProtectHostname=true
ProtectKernelModules=true
ProtectKernelTunables=true
RestrictSUIDSGID=true
LockPersonality=true
ProtectProc=invisible
ProcSubset=pid
IPAddressDeny=169.254.169.254/32
IPAddressDeny=any
IPAddressAllow=127.0.0.1
IPAddressAllow=::1

[Install]
WantedBy=multi-user.target
UNIT

# --- credential rotation timer ---
# STS target role session은 1시간이다. 45분마다 root가 새 값을 발급하고 서비스를
# 재시작해 만료 credential을 사용하지 않게 한다. 서비스 프로세스에는 IMDS deny가 계속
# 적용되므로, restart 이후에도 metadata에서 bootstrap credential을 직접 얻을 수 없다.
# 첫 발화는 부팅 직후(OnBootSec=2min)로 둔다 — 부팅 시점 line 133 이 쓴 runtime creds 로
# 시작한 서비스가 초기 IAM 전파 지연 등으로 DynamoDB Query 를 거부당하면(배포 안정화 #2),
# 이 조기 refresh+restart 가 몇 분 안에 정상 runtime role 로 수렴시킨다(45분 대기 없이).
# refresh 서비스는 After=network-online 이라 네트워크 준비 후 실행된다.
cat > /etc/systemd/system/slackops-runtime-credentials-refresh.service <<'UNIT'
[Unit]
Description=Refresh SlackOps short-lived runtime credentials
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/slackops-refresh-runtime-credentials --force
ExecStartPost=/usr/bin/systemctl try-restart slackops-devops-agent.service slackops-devops-agent-worker.service slackops-devops-agent-chat-agent.service slackops-devops-agent-monitor.service
ExecStartPost=/usr/local/sbin/slackops-security-audit-exporter credential_refresh
UNIT

cat > /etc/systemd/system/slackops-runtime-credentials-refresh.timer <<'UNIT'
[Unit]
Description=Refresh SlackOps runtime credentials before STS expiry

[Timer]
OnBootSec=2min
OnUnitActiveSec=45min
Persistent=true
Unit=slackops-runtime-credentials-refresh.service

[Install]
WantedBy=timers.target
UNIT

cat > /etc/systemd/system/slackops-security-audit-exporter.service <<'UNIT'
[Unit]
Description=Export SlackOps proxy-deny security audit events
After=network-online.target squid.service

[Service]
Type=oneshot
User=root
ExecStart=/usr/local/sbin/slackops-security-audit-exporter proxy_denials
NoNewPrivileges=true
PrivateTmp=true
ProtectHome=true
ProtectSystem=strict
ReadWritePaths=/var/lib/slackops-security-audit
UNIT

cat > /etc/systemd/system/slackops-security-audit-exporter.timer <<'UNIT'
[Unit]
Description=Export SlackOps proxy-deny security audit events every minute

[Timer]
OnBootSec=1min
OnUnitActiveSec=1min
Persistent=true
Unit=slackops-security-audit-exporter.service

[Install]
WantedBy=timers.target
UNIT

systemctl daemon-reload
systemctl enable --now \
  slackops-devops-agent.service \
  slackops-devops-agent-worker.service \
  slackops-devops-agent-chat-agent.service \
  slackops-devops-agent-monitor.service \
  slackops-runtime-credentials-refresh.timer \
  slackops-security-audit-exporter.timer
