#!/usr/bin/env bash
# Vercel 대시보드용 최소권한 IAM 사용자 + Access Key 발급(테이블 스코프).
# ★ 운영자가 직접 실행 — Secret 은 이 출력에만 표시되니 안전 보관(repo/.env 커밋 금지).
# 기본: 읽기 + 승인 쓰기(대시보드 Approve/Reject 라이브). READONLY=1 이면 읽기전용.
set -euo pipefail

export AWS_REGION="${AWS_REGION:-us-east-1}"
USER="${VERCEL_IAM_USER:-slackops-vercel-dashboard}"
TABLE="${DDB_TABLE:-slackops-agent}"

if ! aws sts get-caller-identity >/dev/null 2>&1; then
  echo "vercel-key: ERROR — AWS 자격증명 무효." >&2; exit 1
fi
ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"

if [ "${READONLY:-0}" = "1" ]; then
  ACTIONS='"dynamodb:GetItem","dynamodb:Query"'
  MODE="read-only"
else
  ACTIONS='"dynamodb:GetItem","dynamodb:Query","dynamodb:UpdateItem","dynamodb:PutItem"'
  MODE="read + approve(write)"
fi

echo "vercel-key: user=$USER  mode=$MODE  table=$TABLE  region=$AWS_REGION"

# 1) 사용자(멱등 — 있으면 통과). 콘솔 로그인 없음(프로그래매틱 전용).
aws iam create-user --user-name "$USER" >/dev/null 2>&1 || echo "  (user exists — 재사용)"

# 2) 인라인 정책(테이블 + GSI 스코프, 멱등 overwrite)
aws iam put-user-policy --user-name "$USER" --policy-name dashboard-access \
  --policy-document "{\"Version\":\"2012-10-17\",\"Statement\":[{
    \"Sid\":\"DashboardAccess\",\"Effect\":\"Allow\",\"Action\":[$ACTIONS],
    \"Resource\":[\"arn:aws:dynamodb:${AWS_REGION}:${ACCOUNT}:table/${TABLE}\",
                  \"arn:aws:dynamodb:${AWS_REGION}:${ACCOUNT}:table/${TABLE}/index/*\"]}]}"
echo "  policy 적용됨 ($MODE)"

# 3) Access Key 발급(Secret 은 이때만 표시). 기존 키 2개면 한도 초과 — 먼저 정리 필요.
echo "── 아래 키를 Vercel 환경변수에 입력(Secret 안전 보관) ──"
aws iam create-access-key --user-name "$USER" \
  --query 'AccessKey.{AWS_ACCESS_KEY_ID:AccessKeyId,AWS_SECRET_ACCESS_KEY:SecretAccessKey}' \
  --output table
echo "Vercel env: 위 2개 + DDB_TABLE=$TABLE / AWS_REGION=$AWS_REGION / DASHBOARD_APPROVER=<name>  (DDB_ENDPOINT 미설정!)"
