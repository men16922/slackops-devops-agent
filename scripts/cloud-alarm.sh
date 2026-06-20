#!/usr/bin/env bash
# cloud-alarm.sh — 실 CloudWatch alarm 을 ALARM 으로 강제 → **EventBridge 가 이벤트 구동으로**
# Lambda producer(deploy/lambda)를 호출 → 실시간으로 큐에 제안 적재. (수동 다리 없음 — 이벤트 수신)
#
#   make cloud-lambda-deploy   # (선행 1회) 이벤트 경로 배포: EventBridge rule + Lambda
#   make cloud-alarm           # alarm 발화 → EventBridge → Lambda → DynamoDB 제안(폴링 확인)
#   make cloud-alarm-clean     # 데모 alarm 삭제(비용 정리). 이벤트 경로 정리: make cloud-lambda-clean
#
# 요구: 유효 AWS 자격(aws sts get-caller-identity) + 이벤트 경로 배포됨 + region. 실 DynamoDB.
# 정직한 narration: set-alarm-state 는 alarm 을 "투명하게 강제"(프로덕션은 임계치로 자동 발화).
#   상태 전이 자체가 EventBridge "CloudWatch Alarm State Change" 이벤트를 발행 → 룰이 Lambda 호출.
# 비용: alarm 1개 ~$0.10/월, set/describe 무료, Lambda 호출 무료티어 → 끝나면 make cloud-alarm-clean.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"
[ -f .env ] && { set -a; . ./.env; set +a; }

export PYTHONPATH="${PYTHONPATH:-src}"
export AWS_REGION="${AWS_REGION:-us-east-1}"
unset DDB_ENDPOINT 2>/dev/null || true          # 실 DynamoDB 강제(로컬 8931 아님)

ALARM_NAME="${ALARM_NAME:-slackops-demo-checkout-5xx}"
SERVICE="${SERVICE:-checkout-service}"

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

# 2) 기준선 — 폴링 비교용으로 현재 pending agent 제안 수를 센다.
pending_count() {
  python3 - <<'PY' 2>/dev/null || echo 0
from app.mcp_server import store_from_env, list_pending_impl
import os
svc = os.environ.get("SERVICE", "checkout-service")
n = sum(1 for j in list_pending_impl(store_from_env())
        if j.get("source") == "agent" and j.get("command") == "diagnose" and j.get("args") == svc)
print(n)
PY
}
BEFORE="$(SERVICE="$SERVICE" pending_count)"

# 3) ALARM 강제(투명한 데모) — 상태 전이가 EventBridge 이벤트를 발행한다.
#    reason 에 5xx/error rate/service 마커 포함(Lambda 의 결정적 detect 가 매칭).
REASON="demo: service=$SERVICE ALB 5xx error rate 23% over 5m; upstream 504 gateway timeout; p99 8.1s"
echo "cloud-alarm: set-alarm-state → ALARM (EventBridge 이벤트 발행)…"
aws cloudwatch set-alarm-state --alarm-name "$ALARM_NAME" --state-value ALARM --state-reason "$REASON"

# 4) 폴링 — EventBridge→Lambda 가 큐에 새 제안을 올릴 때까지(최대 ~40s).
echo "cloud-alarm: EventBridge → Lambda → DynamoDB 제안 대기…"
for i in $(seq 1 20); do
  NOW="$(SERVICE="$SERVICE" pending_count)"
  if [ "$NOW" -gt "$BEFORE" ]; then
    echo "cloud-alarm: ✅ 실시간 제안 적재 확인 (pending agent diagnose '$SERVICE': $BEFORE → $NOW)"
    echo "cloud-alarm: done — 대시보드/Slack 에서 제안 확인 → 승인/실행. 정리: make cloud-alarm-clean"
    exit 0
  fi
  sleep 2
done

echo "cloud-alarm: ⚠️  ~40s 내 새 제안 미관측 — 이벤트 경로 점검:" >&2
echo "  · 배포됐나? make cloud-lambda-deploy" >&2
echo "  · Lambda 로그: aws logs tail /aws/lambda/slackops-alarm-producer --since 5m" >&2
echo "  · 이미 동일 open 제안이 있으면 dedupe 로 미증가일 수 있음(정상)." >&2
exit 1
