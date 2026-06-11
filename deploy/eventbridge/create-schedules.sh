#!/usr/bin/env bash
# EventBridge Scheduler — EC2 stop/start 스케줄 (상시 가동 금지 불변).
# 기본: 평일 09:00 start / 19:00 stop (Asia/Seoul). 필요 시 CRON_* 환경변수로 변경.
set -euo pipefail

INSTANCE_ID="${1:?usage: create-schedules.sh <instance-id>}"
ROLE_NAME="${SCHEDULER_ROLE_NAME:-slackops-devops-agent-scheduler-role}"
TZ_NAME="${TZ_NAME:-Asia/Seoul}"
CRON_START="${CRON_START:-cron(0 9 ? * MON-FRI *)}"
CRON_STOP="${CRON_STOP:-cron(0 19 ? * MON-FRI *)}"
DIR="$(cd "$(dirname "$0")" && pwd)"

# Scheduler 실행 역할(태그 조건부 start/stop 만)
if ! aws iam get-role --role-name "$ROLE_NAME" >/dev/null 2>&1; then
  aws iam create-role --role-name "$ROLE_NAME" \
    --assume-role-policy-document "file://$DIR/scheduler-trust-policy.json"
  aws iam put-role-policy --role-name "$ROLE_NAME" \
    --policy-name ec2-start-stop \
    --policy-document "file://$DIR/scheduler-policy.json"
fi
ROLE_ARN="$(aws iam get-role --role-name "$ROLE_NAME" --query Role.Arn --output text)"

make_schedule() {
  local name="$1" cron="$2" action="$3"
  aws scheduler create-schedule \
    --name "$name" \
    --schedule-expression "$cron" \
    --schedule-expression-timezone "$TZ_NAME" \
    --flexible-time-window '{"Mode":"OFF"}' \
    --target "{
      \"Arn\": \"arn:aws:scheduler:::aws-sdk:ec2:${action}\",
      \"RoleArn\": \"$ROLE_ARN\",
      \"Input\": \"{\\\"InstanceIds\\\": [\\\"$INSTANCE_ID\\\"]}\"
    }"
}

make_schedule slackops-agent-start "$CRON_START" startInstances
make_schedule slackops-agent-stop "$CRON_STOP" stopInstances
echo "OK: schedules created for $INSTANCE_ID ($TZ_NAME)"
