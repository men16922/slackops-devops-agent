#!/usr/bin/env bash
# 이벤트 구동 producer 배포 — CloudWatch Alarm(→ALARM) → EventBridge → Lambda → 큐 제안.
# IAM role + Lambda function + EventBridge rule/target/permission 을 멱등 생성/갱신한다.
# 권한: Lambda 는 단일테이블 스코프 쓰기(제안 적재)만 — 실행 안 함(worker + 출력 게이트가 담당).
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

export AWS_REGION="${AWS_REGION:-us-east-1}"
FUNC="${FUNC:-slackops-alarm-producer}"
ROLE="${ROLE:-slackops-alarm-producer-role}"
RULE="${RULE:-slackops-alarm-to-agent}"
TABLE="${DDB_TABLE:-slackops-agent}"
ALARM_PREFIX="${ALARM_PREFIX:-slackops-}"   # 이 prefix alarm 만 반응(다른 계정 alarm 무시 — 안전/비용)
RUNTIME=python3.11
HANDLER=app.alarm_lambda.handler
ZIP="$DIR/alarm-producer.zip"

if ! aws sts get-caller-identity >/dev/null 2>&1; then
  echo "lambda deploy: ERROR — AWS 자격증명 무효." >&2; exit 1
fi
ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"

# 1) zip 빌드
bash "$DIR/build.sh"

# 2) IAM 실행 역할(멱등) — DynamoDB 테이블 스코프 + 로그.
if ! aws iam get-role --role-name "$ROLE" >/dev/null 2>&1; then
  aws iam create-role --role-name "$ROLE" \
    --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]}' >/dev/null
fi
aws iam put-role-policy --role-name "$ROLE" --policy-name alarm-producer-queue \
  --policy-document "{\"Version\":\"2012-10-17\",\"Statement\":[
    {\"Sid\":\"Queue\",\"Effect\":\"Allow\",\"Action\":[\"dynamodb:GetItem\",\"dynamodb:PutItem\",\"dynamodb:UpdateItem\",\"dynamodb:Query\"],
     \"Resource\":[\"arn:aws:dynamodb:${AWS_REGION}:${ACCOUNT}:table/${TABLE}\",\"arn:aws:dynamodb:${AWS_REGION}:${ACCOUNT}:table/${TABLE}/index/*\"]},
    {\"Sid\":\"SlackToken\",\"Effect\":\"Allow\",\"Action\":[\"ssm:GetParameter\"],
     \"Resource\":\"arn:aws:ssm:${AWS_REGION}:${ACCOUNT}:parameter/slackops/*\"},
    {\"Sid\":\"DecryptToken\",\"Effect\":\"Allow\",\"Action\":[\"kms:Decrypt\"],\"Resource\":\"*\"},
    {\"Sid\":\"Logs\",\"Effect\":\"Allow\",\"Action\":[\"logs:CreateLogGroup\",\"logs:CreateLogStream\",\"logs:PutLogEvents\"],\"Resource\":\"arn:aws:logs:*:*:*\"}]}"
ROLE_ARN="$(aws iam get-role --role-name "$ROLE" --query Role.Arn --output text)"

# 3) Lambda function(멱등 create/update)
if aws lambda get-function --function-name "$FUNC" >/dev/null 2>&1; then
  aws lambda update-function-code --function-name "$FUNC" --zip-file "fileb://$ZIP" >/dev/null
  aws lambda wait function-updated-v2 --function-name "$FUNC" 2>/dev/null || true
  aws lambda update-function-configuration --function-name "$FUNC" \
    --handler "$HANDLER" --runtime "$RUNTIME" --timeout 30 \
    --environment "Variables={DDB_TABLE=$TABLE}" >/dev/null
else
  # 최초 생성 시 IAM eventual consistency — role 전파까지 재시도.
  for i in $(seq 1 10); do
    if aws lambda create-function --function-name "$FUNC" --runtime "$RUNTIME" \
        --role "$ROLE_ARN" --handler "$HANDLER" --timeout 30 \
        --environment "Variables={DDB_TABLE=$TABLE}" \
        --zip-file "fileb://$ZIP" >/dev/null 2>&1; then break; fi
    echo "  …IAM role 전파 대기 ($i/10)"; sleep 6
  done
fi
aws lambda wait function-active-v2 --function-name "$FUNC" 2>/dev/null || true
FUNC_ARN="$(aws lambda get-function --function-name "$FUNC" --query Configuration.FunctionArn --output text)"

# 4) EventBridge 룰 — Alarm State Change → ALARM, alarmName prefix 로 스코프.
PATTERN="{\"source\":[\"aws.cloudwatch\"],\"detail-type\":[\"CloudWatch Alarm State Change\"],\"detail\":{\"state\":{\"value\":[\"ALARM\"]},\"alarmName\":[{\"prefix\":\"$ALARM_PREFIX\"}]}}"
aws events put-rule --name "$RULE" --event-pattern "$PATTERN" \
  --description "SlackOps: CloudWatch ALARM -> agent propose (event-driven)" >/dev/null
RULE_ARN="$(aws events describe-rule --name "$RULE" --query Arn --output text)"

# 5) invoke 권한(멱등) + 타깃 연결
aws lambda add-permission --function-name "$FUNC" --statement-id "${RULE}-invoke" \
  --action lambda:InvokeFunction --principal events.amazonaws.com \
  --source-arn "$RULE_ARN" >/dev/null 2>&1 || true
aws events put-targets --rule "$RULE" --targets "Id=1,Arn=$FUNC_ARN" >/dev/null

echo "OK: event-driven producer deployed"
echo "  rule=$RULE  ->  lambda=$FUNC   (alarmName prefix='$ALARM_PREFIX', table=$TABLE)"
echo "  test: make cloud-alarm   (force ALARM -> EventBridge -> Lambda -> DynamoDB proposal)"
