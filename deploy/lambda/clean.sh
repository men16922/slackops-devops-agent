#!/usr/bin/env bash
# 이벤트 구동 producer 정리 — rule/target/permission + Lambda + IAM role 삭제(비용 0 복귀).
set -euo pipefail
export AWS_REGION="${AWS_REGION:-us-east-1}"
FUNC="${FUNC:-slackops-alarm-producer}"
ROLE="${ROLE:-slackops-alarm-producer-role}"
RULE="${RULE:-slackops-alarm-to-agent}"

aws events remove-targets --rule "$RULE" --ids 1 >/dev/null 2>&1 || true
aws events delete-rule --name "$RULE" >/dev/null 2>&1 || true
aws lambda delete-function --function-name "$FUNC" >/dev/null 2>&1 || true
aws iam delete-role-policy --role-name "$ROLE" --policy-name alarm-producer-queue >/dev/null 2>&1 || true
aws iam delete-role --role-name "$ROLE" >/dev/null 2>&1 || true
echo "OK: event-driven producer removed (rule/lambda/role)"
