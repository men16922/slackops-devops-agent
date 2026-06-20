#!/usr/bin/env bash
# DynamoDB 단일테이블 provision — Job/Audit/Telemetry 가 공유하는 control-plane 큐.
# 온디맨드(PAY_PER_REQUEST): EventBridge 스케줄·bursty Slack 워크로드라 용량계획 불필요·idle 시 ~0원.
# GSI 도 테이블 billing-mode(PAY_PER_REQUEST)를 자동 상속 — GSI 별 throughput 지정 없음.
# 스키마 근거: src/app/store/{dynamodb_store,audit_store,telemetry_store}.py
#   PK/SK(테이블) · GSI1(Job status 질의) · GSI2(Job/Audit/Telemetry 일자 feed)
set -euo pipefail

TABLE_NAME="${TABLE_NAME:-slackops-agent}"
REGION="${AWS_REGION:-us-east-1}"

# 멱등: 이미 있으면 생성 생략(ACTIVE 대기만).
if aws dynamodb describe-table --table-name "$TABLE_NAME" --region "$REGION" >/dev/null 2>&1; then
  echo "OK: table '$TABLE_NAME' already exists ($REGION)"
  exit 0
fi

aws dynamodb create-table \
  --table-name "$TABLE_NAME" \
  --region "$REGION" \
  --billing-mode PAY_PER_REQUEST \
  --attribute-definitions \
      AttributeName=PK,AttributeType=S \
      AttributeName=SK,AttributeType=S \
      AttributeName=GSI1PK,AttributeType=S \
      AttributeName=GSI1SK,AttributeType=S \
      AttributeName=GSI2PK,AttributeType=S \
      AttributeName=GSI2SK,AttributeType=S \
  --key-schema \
      AttributeName=PK,KeyType=HASH \
      AttributeName=SK,KeyType=RANGE \
  --global-secondary-indexes \
      'IndexName=GSI1,KeySchema=[{AttributeName=GSI1PK,KeyType=HASH},{AttributeName=GSI1SK,KeyType=RANGE}],Projection={ProjectionType=ALL}' \
      'IndexName=GSI2,KeySchema=[{AttributeName=GSI2PK,KeyType=HASH},{AttributeName=GSI2SK,KeyType=RANGE}],Projection={ProjectionType=ALL}'

echo "waiting for table '$TABLE_NAME' to become ACTIVE ..."
aws dynamodb wait table-exists --table-name "$TABLE_NAME" --region "$REGION"
echo "OK: table '$TABLE_NAME' created (PAY_PER_REQUEST, GSI1+GSI2) in $REGION"
