#!/usr/bin/env bash
# Root-only security-boundary audit exporter. Agent services never receive this role.
set -euo pipefail

AUDIT_ENV_FILE="${AUDIT_ENV_FILE:-/etc/slackops-security-boundary-audit.env}"
LOG_GROUP="${AUDIT_LOG_GROUP:-/slackops/security-boundary-audit}"
LOG_STREAM="${AUDIT_LOG_STREAM:-$(hostname -s)}"
RETENTION_DAYS="${AUDIT_RETENTION_DAYS:-30}"
SQUID_LOG="${SQUID_LOG:-/var/log/squid/access.log}"
STATE_DIR="${AUDIT_STATE_DIR:-/var/lib/slackops-security-audit}"
CURSOR_FILE="$STATE_DIR/squid.offset"

[[ -r "$AUDIT_ENV_FILE" ]] || exit 0
set -a
# shellcheck disable=SC1090
. "$AUDIT_ENV_FILE"
set +a

ensure_sink() {
  # The deployment operator provisions the group and retention. The exporter can
  # only inspect/create streams and append events, so it cannot redirect or
  # reconfigure the audit sink at runtime.
  aws logs describe-log-streams --log-group-name "$LOG_GROUP" --limit 1 >/dev/null
  aws logs create-log-stream --log-group-name "$LOG_GROUP" --log-stream-name "$LOG_STREAM" 2>/dev/null || true
}

emit() {
  local event_type="$1"
  local detail="${2:-}"
  local event_file
  event_file="$(mktemp)"
  jq -cn --arg event_type "$event_type" --arg detail "$detail" \
    --arg host "$(hostname -s)" --arg timestamp "$(date -u +%FT%TZ)" \
    '[{timestamp: (now * 1000 | floor), message: ({event_type: $event_type, detail: $detail, host: $host, timestamp: $timestamp} | tojson)}]' \
    > "$event_file"
  if ! aws logs put-log-events --log-group-name "$LOG_GROUP" --log-stream-name "$LOG_STREAM" \
    --log-events "file://$event_file"; then
    rm -f "$event_file"
    return 1
  fi
  rm -f "$event_file"
}

export_credential_refresh() {
  emit "credential_refresh" "runtime_and_audit_credentials_rotated"
}

export_proxy_denials() {
  [[ -f "$SQUID_LOG" ]] || exit 0
  install -d -m 700 "$STATE_DIR"
  local size offset line status
  size="$(stat -c %s "$SQUID_LOG")"
  offset=0
  [[ -f "$CURSOR_FILE" ]] && offset="$(cat "$CURSOR_FILE")"
  (( offset <= size )) || offset=0
  while IFS= read -r line; do
    status="$(awk '{print $4}' <<<"$line")"
    [[ "$status" == TCP_DENIED/* ]] || continue
    # Do not export the requested URL: it can contain untrusted query data or secrets.
    emit "proxy_denied" "squid_status=$status"
  done < <(tail -c "+$((offset + 1))" "$SQUID_LOG")
  printf '%s\n' "$size" > "$CURSOR_FILE"
}

ensure_sink
case "${1:-proxy_denials}" in
  credential_refresh) export_credential_refresh ;;
  proxy_denials) export_proxy_denials ;;
  *) echo "usage: $0 [credential_refresh|proxy_denials]" >&2; exit 2 ;;
esac
