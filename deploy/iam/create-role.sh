#!/usr/bin/env bash
# SlackOps IAM role set 생성/동기화.
#
# EC2 Instance Profile은 bootstrap만 담당한다: SSM의 부팅 secret 읽기 + 두 개의
# same-account role 전환. 실제 서비스는 runtime role, Claude가 기동하는 SlackOps MCP는
# DynamoDB proposal queue 전용 control-plane role의 단기 credential만 사용한다.
set -euo pipefail

ROLE_NAME="${ROLE_NAME:-slackops-devops-agent-role}"
PROFILE_NAME="${PROFILE_NAME:-slackops-devops-agent-profile}"
POLICY_NAME="${POLICY_NAME:-slackops-devops-agent-bootstrap}"
LEGACY_POLICY_NAME="${LEGACY_POLICY_NAME:-slackops-devops-agent-ro}"
RUNTIME_ROLE_NAME="${RUNTIME_ROLE_NAME:-slackops-devops-agent-runtime-role}"
MCP_ROLE_NAME="${MCP_ROLE_NAME:-slackops-devops-agent-mcp-role}"
AUDIT_ROLE_NAME="${AUDIT_ROLE_NAME:-slackops-devops-agent-audit-role}"
AUDIT_LOG_GROUP="${AUDIT_LOG_GROUP:-/slackops/security-boundary-audit}"
DIR="$(cd "$(dirname "$0")" && pwd)"
ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
AWS_REGION="${AWS_REGION:-$(aws configure get region || true)}"
AWS_REGION="${AWS_REGION:-us-east-1}"
BOOTSTRAP_ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${ROLE_NAME}"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

render_policy() {
  local source="$1"
  local target="$2"
  sed \
    -e "s|__ACCOUNT_ID__|${ACCOUNT_ID}|g" \
    -e "s|__REGION__|${AWS_REGION}|g" \
    "$source" > "$target"
}

render_trust_policy() {
  sed "s|__BOOTSTRAP_ROLE_ARN__|${BOOTSTRAP_ROLE_ARN}|g" \
    "$DIR/runtime-role-trust-policy.json" > "$1"
}

ensure_role() {
  local name="$1"
  local trust="$2"
  local description="$3"
  if aws iam get-role --role-name "$name" >/dev/null 2>&1; then
    aws iam update-assume-role-policy --role-name "$name" \
      --policy-document "file://$trust"
  else
    aws iam create-role --role-name "$name" --assume-role-policy-document "file://$trust" \
      --description "$description" >/dev/null
  fi
  # 한 시간 단기 credential을 사용하는 refresh timer가 기본으로 동작한다. 최대 세션도
  # 한 시간으로 고정해 장기 role chaining을 허용하지 않는다.
  aws iam update-role --role-name "$name" --max-session-duration 3600
}

BOOTSTRAP_POLICY="$TMP_DIR/bootstrap-policy.json"
RUNTIME_POLICY="$TMP_DIR/runtime-policy.json"
MCP_POLICY="$TMP_DIR/mcp-policy.json"
AUDIT_POLICY="$TMP_DIR/audit-policy.json"
RUNTIME_TRUST="$TMP_DIR/runtime-trust.json"
render_policy "$DIR/instance-profile-policy.json" "$BOOTSTRAP_POLICY"
render_policy "$DIR/runtime-role-policy.json" "$RUNTIME_POLICY"
render_policy "$DIR/mcp-control-plane-policy.json" "$MCP_POLICY"
render_policy "$DIR/audit-role-policy.json" "$AUDIT_POLICY"
render_trust_policy "$RUNTIME_TRUST"

# 먼저 target role을 완성한다. 중간 실패 시 기존 bootstrap role의 권한을 성급히 축소해
# 이미 실행 중인 배포를 멈추지 않는다.
ensure_role "$ROLE_NAME" "$DIR/trust-policy.json" \
  "SlackOps EC2 bootstrap role (secret read + role switch only)"
ensure_role "$RUNTIME_ROLE_NAME" "$RUNTIME_TRUST" \
  "SlackOps EC2 runtime role (fixed read adapters + control plane)"
ensure_role "$MCP_ROLE_NAME" "$RUNTIME_TRUST" \
  "SlackOps internal MCP control-plane role (DynamoDB proposal queue only)"
ensure_role "$AUDIT_ROLE_NAME" "$RUNTIME_TRUST" \
  "SlackOps root-only security-boundary audit exporter"

aws iam put-role-policy --role-name "$RUNTIME_ROLE_NAME" \
  --policy-name slackops-devops-agent-runtime --policy-document "file://$RUNTIME_POLICY"
aws iam put-role-policy --role-name "$MCP_ROLE_NAME" \
  --policy-name slackops-devops-agent-mcp --policy-document "file://$MCP_POLICY"
aws iam put-role-policy --role-name "$AUDIT_ROLE_NAME" \
  --policy-name slackops-devops-agent-audit --policy-document "file://$AUDIT_POLICY"
aws iam put-role-policy --role-name "$ROLE_NAME" --policy-name "$POLICY_NAME" \
  --policy-document "file://$BOOTSTRAP_POLICY"

# The deployment operator, not the runtime audit role, owns sink creation and
# retention. This prevents a compromised exporter from creating or reconfiguring
# alternate audit destinations.
if ! CREATE_OUTPUT="$(aws logs create-log-group --region "$AWS_REGION" --log-group-name "$AUDIT_LOG_GROUP" 2>&1)"; then
  if [[ "$CREATE_OUTPUT" != *"ResourceAlreadyExistsException"* ]]; then
    echo "$CREATE_OUTPUT" >&2
    exit 1
  fi
fi
aws logs put-retention-policy --region "$AWS_REGION" --log-group-name "$AUDIT_LOG_GROUP" --retention-in-days 30

# 이전 단일-role 정책이 남아 있으면 bootstrap 축소가 무효가 된다. 신규 policy가 성공한
# 뒤에만 제거해 migration 중 권한 공백을 피한다.
if [[ "$LEGACY_POLICY_NAME" != "$POLICY_NAME" ]]; then
  aws iam delete-role-policy --role-name "$ROLE_NAME" --policy-name "$LEGACY_POLICY_NAME" \
    2>/dev/null || true
fi

if ! aws iam get-instance-profile --instance-profile-name "$PROFILE_NAME" >/dev/null 2>&1; then
  aws iam create-instance-profile --instance-profile-name "$PROFILE_NAME" >/dev/null
fi
PROFILE_ROLE="$(aws iam get-instance-profile --instance-profile-name "$PROFILE_NAME" \
  --query 'InstanceProfile.Roles[0].RoleName' --output text)"
if [[ "$PROFILE_ROLE" == "None" ]]; then
  aws iam add-role-to-instance-profile --instance-profile-name "$PROFILE_NAME" --role-name "$ROLE_NAME"
elif [[ "$PROFILE_ROLE" != "$ROLE_NAME" ]]; then
  echo "ERROR: instance profile $PROFILE_NAME already contains unexpected role $PROFILE_ROLE" >&2
  exit 1
fi

echo "OK: bootstrap=$ROLE_NAME runtime=$RUNTIME_ROLE_NAME mcp=$MCP_ROLE_NAME audit=$AUDIT_ROLE_NAME profile=$PROFILE_NAME"
