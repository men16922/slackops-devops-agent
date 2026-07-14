#!/usr/bin/env bash
# Sync the local source-of-truth approver allowlist to the SSM value consumed
# by EC2 user-data and the Slack application service.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ENV_FILE="$REPO_ROOT/.env"
REGION="${AWS_REGION:-us-east-1}"
PARAMETER_NAME="/slackops/SLACK_APPROVER_IDS"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "slack-approvers: ERROR — missing $ENV_FILE" >&2
  exit 1
fi
if ! command -v aws >/dev/null 2>&1; then
  echo "slack-approvers: ERROR — AWS CLI is required." >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

if [[ -z "${SLACK_APPROVER_IDS:-}" ]]; then
  echo "slack-approvers: ERROR — SLACK_APPROVER_IDS must be set in .env" >&2
  exit 1
fi

aws sts get-caller-identity --region "$REGION" >/dev/null
version="$(aws ssm put-parameter \
  --region "$REGION" \
  --name "$PARAMETER_NAME" \
  --type SecureString \
  --value "$SLACK_APPROVER_IDS" \
  --overwrite \
  --query Version \
  --output text)"
echo "slack-approvers: synced $PARAMETER_NAME (version $version; value hidden)"
