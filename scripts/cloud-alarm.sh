#!/usr/bin/env bash
# cloud-alarm.sh — 실 CloudWatch alarm 을 강제 발화시키고, 그 alarm 을 신호로 에이전트가
# diagnose 를 제안하게 한다(클라우드 데모). alarm→EventBridge 자동 적재는 roadmap 이라
# 이 스크립트가 describe-alarms → monitor "다리"를 놓는다 — 제안은 **실 DynamoDB 큐**로 간다.
#
#   make cloud-alarm                 # Tier1(결정적, 무료) — alarm 강제 → 규칙 엔진이 제안
#   make cloud-alarm ARGS=--real     # Tier2 — Claude 가 AWS MCP 로 alarm 직접 조회해 제안(~$0.1 구독)
#   make cloud-alarm-clean           # 데모 alarm 삭제(비용 정리)
#
# 요구: 유효 AWS 자격(aws sts get-caller-identity) + region. 실 DynamoDB(DDB_ENDPOINT 미설정).
# 정직한 narration: set-alarm-state 는 alarm 을 "투명하게 강제" — 프로덕션은 임계치로 자동 발화.
# 비용: alarm 1개 ~$0.10/월(며칠 ~$0.01), set/describe-alarms 무료 → 끝나면 make cloud-alarm-clean.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"
[ -f .env ] && { set -a; . ./.env; set +a; }   # AWS_REGION / (선택)CLAUDE 토큰

export PYTHONPATH="${PYTHONPATH:-src}"
export AWS_REGION="${AWS_REGION:-us-east-1}"
unset DDB_ENDPOINT 2>/dev/null || true          # 실 DynamoDB 강제(로컬 8931 아님)

ALARM_NAME="${ALARM_NAME:-slackops-demo-checkout-5xx}"
SERVICE="${SERVICE:-checkout-service}"
SIGFILE="$(mktemp -t slackops-alarm.XXXXXX)"
trap 'rm -f "$SIGFILE"' EXIT

if ! aws sts get-caller-identity >/dev/null 2>&1; then
  echo "cloud-alarm: ERROR — AWS 자격증명 무효. aws configure / aws sso login 후 재시도." >&2
  exit 1
fi

# 1) 데모 alarm 보장(없으면 생성 — 합성 메트릭, 실 리소스 불필요). put 은 멱등.
echo "cloud-alarm: alarm 보장 — $ALARM_NAME (synthetic metric)…"
aws cloudwatch put-metric-alarm \
  --alarm-name "$ALARM_NAME" \
  --alarm-description "SlackOps demo — $SERVICE 5xx (synthetic; forced via set-alarm-state)" \
  --namespace "SlackOpsDemo" --metric-name "Http5xxRate" \
  --statistic Average --period 60 --evaluation-periods 1 \
  --threshold 5 --comparison-operator GreaterThanThreshold \
  --treat-missing-data notBreaching

# 2) ALARM 강제(투명한 데모) — reason 에 5xx/error rate 키워드 포함(Tier1 규칙 매칭).
REASON="demo: service=$SERVICE ALB 5xx error rate 23% over 5m; upstream 504 gateway timeout; p99 8.1s"
echo "cloud-alarm: set-alarm-state → ALARM…"
aws cloudwatch set-alarm-state --alarm-name "$ALARM_NAME" --state-value ALARM --state-reason "$REASON"

# 3) 실 alarm 을 읽어(describe-alarms) 신호 텍스트로 — "에이전트가 alarm 을 본다".
STATE_REASON="$(aws cloudwatch describe-alarms --alarm-names "$ALARM_NAME" \
  --query 'MetricAlarms[0].StateReason' --output text)"
printf 'service=%s CloudWatch alarm %s in ALARM — %s\n' \
  "$SERVICE" "$ALARM_NAME" "$STATE_REASON" > "$SIGFILE"
echo "cloud-alarm: 신호 → $(cat "$SIGFILE")"

# 4) 에이전트 제안(실 DynamoDB 큐) → EC2 worker 실행 + Slack 알림.  ARGS=--real 면 Tier2.
echo "cloud-alarm: agent_monitor → 실 DynamoDB 큐에 제안…"
python3 -m app.agent_monitor --signals-file "$SIGFILE" "$@"

echo "cloud-alarm: done — 대시보드/Slack 에서 제안 확인 → 승인/실행. 정리: make cloud-alarm-clean"
