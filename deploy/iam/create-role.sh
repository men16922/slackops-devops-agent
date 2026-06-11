#!/usr/bin/env bash
# IAM Role + Instance Profile 생성 (읽기 전용 기준 + OTel export).
# Access Key 절대 발급/저장 금지 — Instance Profile 만.
set -euo pipefail

ROLE_NAME="${ROLE_NAME:-slackops-devops-agent-role}"
PROFILE_NAME="${PROFILE_NAME:-slackops-devops-agent-profile}"
POLICY_NAME="${POLICY_NAME:-slackops-devops-agent-ro}"
DIR="$(cd "$(dirname "$0")" && pwd)"

aws iam create-role \
  --role-name "$ROLE_NAME" \
  --assume-role-policy-document "file://$DIR/trust-policy.json" \
  --description "slackops-devops-agent EC2 instance role (read-only + OTel export)"

aws iam put-role-policy \
  --role-name "$ROLE_NAME" \
  --policy-name "$POLICY_NAME" \
  --policy-document "file://$DIR/instance-profile-policy.json"

aws iam create-instance-profile --instance-profile-name "$PROFILE_NAME"
aws iam add-role-to-instance-profile \
  --instance-profile-name "$PROFILE_NAME" \
  --role-name "$ROLE_NAME"

echo "OK: role=$ROLE_NAME profile=$PROFILE_NAME"
