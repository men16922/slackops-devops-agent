#!/usr/bin/env bash
# Remove the demo CloudWatch log group created by seed-demo-logs.sh (post-demo cleanup).
set -euo pipefail

REGION="${AWS_REGION:-us-east-1}"
GROUP="${DEMO_LOG_GROUP:-/aws/slackops-demo/checkout-service}"

aws logs delete-log-group --log-group-name "$GROUP" --region "$REGION" 2>/dev/null \
  && echo "deleted log group: $GROUP" \
  || echo "log group not present (nothing to delete): $GROUP"
