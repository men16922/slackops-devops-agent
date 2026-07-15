#!/usr/bin/env bash
# EC2 bootstrap role로부터 단기 runtime/MCP credential을 발급해 root-only 환경 파일에 기록한다.
#
# 이 스크립트만 IMDS에 접근한다. SlackOps 서비스와 Claude 자식 프로세스는 IMDS가 차단되고,
# 이 파일에 기록된 단기 credential을 환경으로만 받는다. 기본 45분 재사용/1시간 만료로
# credential rotation과 서비스 재시작 사이에 여유를 둔다.
set -euo pipefail

RUNTIME_ROLE_NAME="${RUNTIME_ROLE_NAME:-slackops-devops-agent-runtime-role}"
MCP_ROLE_NAME="${MCP_ROLE_NAME:-slackops-devops-agent-mcp-role}"
AUDIT_ROLE_NAME="${AUDIT_ROLE_NAME:-slackops-devops-agent-audit-role}"
ENV_FILE="${ENV_FILE:-/etc/slackops-devops-agent.runtime.env}"
AUDIT_ENV_FILE="${AUDIT_ENV_FILE:-/etc/slackops-security-boundary-audit.env}"
MAX_AGE_S="${MAX_AGE_S:-2700}"
LOCK_FILE="${LOCK_FILE:-/run/lock/slackops-runtime-credentials.lock}"
FORCE=false

if [[ "${1:-}" == "--force" ]]; then
  FORCE=true
fi

is_fresh() {
  [[ -f "$ENV_FILE" ]] || return 1
  local now modified
  now="$(date +%s)"
  modified="$(stat -c %Y "$ENV_FILE")"
  (( now - modified < MAX_AGE_S ))
}

if [[ "$FORCE" == false ]] && is_fresh; then
  exit 0
fi

mkdir -p "$(dirname "$LOCK_FILE")"
exec 9>"$LOCK_FILE"
flock -x 9
if [[ "$FORCE" == false ]] && is_fresh; then
  exit 0
fi

# 이 프로세스는 root bootstrap 경로다. 상속된 disable flag가 있어도 source credential을
# 읽을 수 있게 제거한다.
unset AWS_EC2_METADATA_DISABLED AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN AWS_PROFILE
IMDS_TOKEN="$(curl -fsSL -X PUT http://169.254.169.254/latest/api/token \
  -H 'X-aws-ec2-metadata-token-ttl-seconds: 300')"
REGION="$(curl -fsSL -H "X-aws-ec2-metadata-token: $IMDS_TOKEN" \
  http://169.254.169.254/latest/meta-data/placement/region)"
ACCOUNT_ID="$(aws sts get-caller-identity --region "$REGION" --query Account --output text)"

assume_role() {
  local role_name="$1"
  local session_name="$2"
  aws sts assume-role --region "$REGION" \
    --role-arn "arn:aws:iam::${ACCOUNT_ID}:role/${role_name}" \
    --role-session-name "$session_name" --duration-seconds 3600 \
    --query 'Credentials.[AccessKeyId,SecretAccessKey,SessionToken]' --output text
}

read -r RUNTIME_ACCESS_KEY RUNTIME_SECRET_KEY RUNTIME_SESSION_TOKEN < <(
  assume_role "$RUNTIME_ROLE_NAME" slackops-runtime
)
read -r MCP_ACCESS_KEY MCP_SECRET_KEY MCP_SESSION_TOKEN < <(
  assume_role "$MCP_ROLE_NAME" slackops-mcp
)
read -r AUDIT_ACCESS_KEY AUDIT_SECRET_KEY AUDIT_SESSION_TOKEN < <(
  assume_role "$AUDIT_ROLE_NAME" slackops-security-audit
)

TMP_FILE="$(mktemp "${ENV_FILE}.XXXXXX")"
trap 'rm -f "$TMP_FILE"' EXIT
umask 077
{
  printf 'AWS_REGION=%s\n' "$REGION"
  printf 'AWS_DEFAULT_REGION=%s\n' "$REGION"
  printf 'AWS_ACCESS_KEY_ID=%s\n' "$RUNTIME_ACCESS_KEY"
  printf 'AWS_SECRET_ACCESS_KEY=%s\n' "$RUNTIME_SECRET_KEY"
  printf 'AWS_SESSION_TOKEN=%s\n' "$RUNTIME_SESSION_TOKEN"
  # 서비스는 직접 IMDS fallback을 하지 않는다. child도 이 값을 상속하지만 claude_runner가
  # credential 자체를 제거해 모델에는 전달하지 않는다.
  printf 'AWS_EC2_METADATA_DISABLED=true\n'
  # 내부 SlackOps MCP stdio server에만 전달할 DynamoDB queue 전용 credential.
  printf 'SLACKOPS_MCP_AWS_ACCESS_KEY_ID=%s\n' "$MCP_ACCESS_KEY"
  printf 'SLACKOPS_MCP_AWS_SECRET_ACCESS_KEY=%s\n' "$MCP_SECRET_KEY"
  printf 'SLACKOPS_MCP_AWS_SESSION_TOKEN=%s\n' "$MCP_SESSION_TOKEN"
} > "$TMP_FILE"
chmod 600 "$TMP_FILE"
chown root:root "$TMP_FILE"
mv -f "$TMP_FILE" "$ENV_FILE"
AUDIT_TMP_FILE="$(mktemp "${AUDIT_ENV_FILE}.XXXXXX")"
{
  printf 'AWS_REGION=%s\n' "$REGION"
  printf 'AWS_DEFAULT_REGION=%s\n' "$REGION"
  printf 'AWS_ACCESS_KEY_ID=%s\n' "$AUDIT_ACCESS_KEY"
  printf 'AWS_SECRET_ACCESS_KEY=%s\n' "$AUDIT_SECRET_KEY"
  printf 'AWS_SESSION_TOKEN=%s\n' "$AUDIT_SESSION_TOKEN"
  printf 'AWS_EC2_METADATA_DISABLED=true\n'
} > "$AUDIT_TMP_FILE"
chmod 600 "$AUDIT_TMP_FILE"
chown root:root "$AUDIT_TMP_FILE"
mv -f "$AUDIT_TMP_FILE" "$AUDIT_ENV_FILE"
trap - EXIT
