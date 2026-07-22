#!/usr/bin/env bash
# Seed a demo CloudWatch log group with realistic checkout-service 5xx events so the
# LIVE diagnose demo reaches the read-only evidence path.
#
# Why this exists: policy_boundary allows logs/diagnose only for log groups under the
# reviewed prefix SLACKOPS_ALLOWED_LOG_GROUP_PREFIXES (=/aws/ on EC2). A fictional
# "checkout-service" name is denied as resource_not_allowed *before* any fetch. This
# creates a real, in-prefix group (/aws/slackops-demo/...) the runtime role can read
# (CloudWatchReadOnly: Describe*/Get*/List* on *), so the diagnosis returns real evidence.
#
# No IAM change is needed. Clean up with deploy/demo/clean-demo-logs.sh after the demo.
set -euo pipefail

REGION="${AWS_REGION:-us-east-1}"
GROUP="${DEMO_LOG_GROUP:-/aws/slackops-demo/checkout-service}"
STREAM="${DEMO_LOG_STREAM:-ecs/checkout-service/$(date +%Y%m%d-%H%M%S)}"

# Idempotent group create + short retention (demo data must not linger / add cost).
aws logs create-log-group --log-group-name "$GROUP" --region "$REGION" 2>/dev/null \
  && echo "created log group: $GROUP" \
  || echo "log group already exists: $GROUP"
aws logs put-retention-policy --log-group-name "$GROUP" --retention-in-days 1 --region "$REGION" >/dev/null || true
aws logs create-log-stream --log-group-name "$GROUP" --log-stream-name "$STREAM" --region "$REGION"

# Build a coherent incident: payment-service (downstream) degrades -> connection pool
# exhaustion -> circuit breaker opens -> checkout-service returns 5xx. Timestamps land
# in the last few minutes so the fetcher's now-24h window includes them.
EVENTS_JSON="$(python3 - <<'PY'
import json, time
now = int(time.time() * 1000)
lines = [
    "INFO  [checkout-service] request POST /api/v1/checkout order=ord_8f21 user=u_4471",
    "WARN  [checkout-service] payment-service call p99 latency 6200ms (soft threshold 500ms)",
    "ERROR [checkout-service] HTTP 502 Bad Gateway - upstream payment-service timed out after 30000ms (POST /api/v1/checkout)",
    "WARN  [checkout-service] db connection pool near capacity: active=18 max=20 idle=0",
    "ERROR [checkout-service] HTTP 500 Internal Server Error - connection pool exhausted (max=20 active=20 wait_timeout=2000ms)",
    "ERROR [checkout-service] HTTP 502 Bad Gateway - upstream payment-service timed out after 30000ms (POST /api/v1/checkout)",
    "WARN  [checkout-service] circuit breaker HALF_OPEN for payment-service after 5 consecutive failures",
    "ERROR [checkout-service] HTTP 503 Service Unavailable - circuit breaker OPEN for payment-service, shedding load",
    "ERROR [checkout-service] HTTP 500 Internal Server Error - unhandled PaymentGatewayException: read timed out",
    "ERROR [checkout-service] HTTP 503 Service Unavailable - circuit breaker OPEN for payment-service, shedding load",
    "INFO  [checkout-service] health check /healthz degraded: dependency payment-service=UNHEALTHY",
    "ERROR [checkout-service] HTTP 502 Bad Gateway - upstream payment-service timed out after 30000ms (POST /api/v1/checkout)",
]
events = [
    {"timestamp": now - (len(lines) - i) * 1000, "message": m}
    for i, m in enumerate(lines)
]
print(json.dumps(events))
PY
)"

aws logs put-log-events \
  --log-group-name "$GROUP" \
  --log-stream-name "$STREAM" \
  --log-events "$EVENTS_JSON" \
  --region "$REGION" >/dev/null

echo "seeded $(echo "$EVENTS_JSON" | python3 -c 'import sys,json;print(len(json.load(sys.stdin)))') events into $GROUP / $STREAM"
echo "LIVE diagnose target: $GROUP"
