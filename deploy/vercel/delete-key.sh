#!/usr/bin/env bash
# Vercel 대시보드 IAM 사용자/키 정리 — 노출 의심·제출 후 사용.
set -euo pipefail
export AWS_REGION="${AWS_REGION:-us-east-1}"
USER="${VERCEL_IAM_USER:-slackops-vercel-dashboard}"

for k in $(aws iam list-access-keys --user-name "$USER" --query 'AccessKeyMetadata[].AccessKeyId' --output text 2>/dev/null); do
  aws iam delete-access-key --user-name "$USER" --access-key-id "$k" >/dev/null 2>&1 || true
  echo "  deleted key $k"
done
aws iam delete-user-policy --user-name "$USER" --policy-name dashboard-access >/dev/null 2>&1 || true
aws iam delete-user --user-name "$USER" >/dev/null 2>&1 || true
echo "OK: $USER 정리 완료"
