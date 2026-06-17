#!/usr/bin/env bash
#
# run.sh — unattended overnight loop runner (single-engine, Claude Code)
# ----------------------------------------------------------------------------
# Calls headless Claude Code one iteration at a time. Each iteration restores
# state from a small context (/sync) → implements ONE [auto] task and passes the
# gate → records it (/checkpoint) → makes a local commit. Because every iteration
# commits, stopping at any point loses at most one iteration of work.
#
# Usage:
#   caffeinate -dimsu scripts/overnight/run.sh &     # macOS: prevent sleep + background
#   scripts/overnight/run.sh --once                  # single iteration (smoke test)
#   touch scripts/overnight/STOP                      # graceful stop (after current iter)
#   tail -f scripts/overnight/logs/runner.log         # observe
#   # in the morning: run /overnight-report in a Claude session
#
# Exit conditions: DONE (backlog drained/all-blocked) · STOP (manual) ·
#   MAX_ITER reached · MAX_CONSEC_FAIL consecutive failures · MAX_NO_PROGRESS no-commit iters.
#
# Safety: each iteration runs ONLY under scripts/overnight/overnight-settings.json
#   (deny: git push / network / destructive make / Web/MCP). Interactive settings untouched.
#
# This is the single-engine (Claude) template installed by the overnight-harness plugin.
# Multi-engine (codex/agy worktrees + lanes) lives in the full harness — out of scope here.
# ----------------------------------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR" && git rev-parse --show-toplevel 2>/dev/null || true)"
[ -n "$REPO_ROOT" ] || REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$REPO_ROOT"

# --- Paths (relative to REPO_ROOT — must match overnight-settings.json allow patterns) ---
PROMPT_FILE="scripts/overnight/PROMPT.md"
SETTINGS_FILE="scripts/overnight/overnight-settings.json"   # claude permission boundary
STOP_FILE="scripts/overnight/STOP"
DONE_FILE="scripts/overnight/DONE"
LOG_DIR="scripts/overnight/logs"
RUNNER_LOG="$LOG_DIR/runner.log"
STATUS_TSV="$LOG_DIR/status.tsv"   # machine-readable iteration ledger (status.sh/dashboard)

# --- Tunable environment variables ---
: "${PROJECT_NAME:=$(basename "$REPO_ROOT")}"  # used in notifications
: "${MAX_ITER:=20}"             # total iteration cap (runaway backstop)
: "${ITER_TIMEOUT:=1800}"       # max seconds per iteration
: "${LIMIT_WAIT:=1800}"         # wait seconds on usage/session-limit detection
: "${PAUSE:=30}"                # seconds between iterations
: "${MAX_CONSEC_FAIL:=3}"       # safe-stop after N consecutive failures
: "${MAX_NO_PROGRESS:=2}"       # safe-stop after N successes with no new commit (thin-backlog exit)
: "${KEEP_ITER_LOGS:=30}"       # keep only the most recent N iter-*.log
: "${GATE_CMD:=make check}"     # commit gate (green). Override per repo: GATE_CMD="make test" etc.
export GATE_CMD                 # PROMPT.md references $GATE_CMD

ONCE=0
[ "${1:-}" = "--once" ] && ONCE=1

mkdir -p "$LOG_DIR"

log() {
  printf '%s  %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$1" | tee -a "$RUNNER_LOG"
}

# Machine-readable iteration ledger (tab-separated): ts engine branch iter outcome head dur(s)
emit_status() {
  local outcome="$1" head="${2:-}" dur="${3:-}" branch
  branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?')"
  [ -f "$STATUS_TSV" ] || printf 'ts\tengine\tbranch\titer\toutcome\thead\tdur\n' > "$STATUS_TSV"
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
    "$(date '+%Y-%m-%dT%H:%M:%S')" "claude" "$branch" "$iter" "$outcome" "${head:0:9}" "$dur" >> "$STATUS_TSV"
}

# Email host notification ONLY on failure-class exits (not on success/clean exits — avoids spam).
# Transport/recipient is scripts/overnight/notify.sh (SMTP or macOS Mail). Notify failure never kills the runner.
notify_failure() {
  local reason="$1"
  local branch recent body
  branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?')"
  recent="$(git log --oneline -5 2>/dev/null)"
  body="The $PROJECT_NAME overnight loop exited in a state that needs review.

branch   : $branch
reason   : $reason
iters    : $iter
time     : $(date '+%Y-%m-%d %H:%M:%S')

recent commits:
$recent

last iteration log: ${ITER_LOG:-(none)} (check HEAD residuals / Blocker). Morning review: /overnight-report."
  bash scripts/overnight/notify.sh "[$PROJECT_NAME overnight] needs review — $reason" "$body" \
    >> "$RUNNER_LOG" 2>&1 || true
}

# --- timeout binary detection (macOS uses coreutils' gtimeout) ---
TIMEOUT_BIN=""
if command -v gtimeout >/dev/null 2>&1; then
  TIMEOUT_BIN="gtimeout"
elif command -v timeout >/dev/null 2>&1; then
  TIMEOUT_BIN="timeout"
fi

# --- preflight ---
command -v claude >/dev/null 2>&1 || { log "FATAL: 'claude' CLI not found on PATH — exit"; exit 1; }
[ -f "$SETTINGS_FILE" ] || { log "FATAL: $SETTINGS_FILE missing — exit"; exit 1; }
[ -f "$PROMPT_FILE" ]   || { log "FATAL: $PROMPT_FILE missing — exit"; exit 1; }
[ -n "$TIMEOUT_BIN" ] || log "WARN: no gtimeout/timeout — per-iteration timeout disabled (brew install coreutils)"

PROMPT_CONTENT="$(cat "$PROMPT_FILE")"

# Keep only the most recent KEEP_ITER_LOGS iter-*.log
prune_logs() {
  local logs
  logs="$(ls -1t "$LOG_DIR"/iter-*.log 2>/dev/null)" || return 0
  [ -z "$logs" ] && return 0
  printf '%s\n' "$logs" | tail -n +"$((KEEP_ITER_LOGS + 1))" | while read -r f; do
    [ -n "$f" ] && rm -f "$f"
  done
}

# Classify iteration outcome: success / limit / failure
#  1) --output-format json object with is_error==false → success
#  2) only when not success, check limit markers → limit
#  3) otherwise rc≠0 → failure, else success
classify_outcome() {
  python3 - "$1" "$2" <<'PY'
import sys, json
rc = int(sys.argv[1])
try:
    with open(sys.argv[2], "r", errors="replace") as f:
        text = f.read()
except OSError:
    text = ""

obj = None
try:
    cand = json.loads(text)
    if isinstance(cand, dict):
        obj = cand
except Exception:
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            cand = json.loads(line)
            if isinstance(cand, dict):
                obj = cand
        except Exception:
            pass

if isinstance(obj, dict) and obj.get("is_error") is False:
    print("success"); sys.exit(0)

low = text.lower()
markers = ["usage limit", "session limit", "rate limit", "overloaded",
           "hit your", "too many requests", "quota"]
if any(m in low for m in markers):
    print("limit"); sys.exit(0)

print("failure" if rc != 0 else "success")
PY
}

log "=== overnight loop start (engine=claude, branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null), gate='$GATE_CMD', MAX_ITER=$MAX_ITER, once=$ONCE) ==="

iter=0
consec_fail=0
no_progress=0
exit_reason="unknown"

while :; do
  if [ -f "$STOP_FILE" ]; then
    exit_reason="STOP ($(cat "$STOP_FILE" 2>/dev/null | head -1))"; log "STOP detected — graceful exit"; break
  fi
  if [ -f "$DONE_FILE" ]; then
    exit_reason="DONE ($(cat "$DONE_FILE" 2>/dev/null | head -1))"; log "DONE detected — exit"; break
  fi
  if [ "$iter" -ge "$MAX_ITER" ]; then
    exit_reason="MAX_ITER ($MAX_ITER)"; log "MAX_ITER reached — exit"; break
  fi

  iter=$((iter + 1))
  prune_logs || true

  HEAD_BEFORE="$(git rev-parse HEAD 2>/dev/null || echo none)"
  ITER_LOG="$LOG_DIR/iter-$iter.log"
  ITER_START="$(date +%s)"
  log "iteration $iter start (HEAD=${HEAD_BEFORE:0:9})"
  emit_status "running" "$HEAD_BEFORE" ""

  set +e
  $TIMEOUT_BIN ${TIMEOUT_BIN:+$ITER_TIMEOUT} claude -p "$PROMPT_CONTENT" \
    --permission-mode acceptEdits \
    --settings "$SETTINGS_FILE" \
    --output-format json > "$ITER_LOG" 2>&1
  rc=$?
  set -e

  outcome="$(classify_outcome "$rc" "$ITER_LOG" || echo failure)"
  ITER_DUR=$(( $(date +%s) - ITER_START ))
  HEAD_NOW="$(git rev-parse HEAD 2>/dev/null || echo none)"
  log "iteration $iter result: $outcome (rc=$rc)"
  emit_status "$outcome" "$HEAD_NOW" "$ITER_DUR"

  case "$outcome" in
    limit)
      consec_fail=0
      log "limit detected — waiting ${LIMIT_WAIT}s before retry"
      sleep "$LIMIT_WAIT"
      continue
      ;;
    failure)
      consec_fail=$((consec_fail + 1))
      log "failure count $consec_fail/$MAX_CONSEC_FAIL"
      if [ "$consec_fail" -ge "$MAX_CONSEC_FAIL" ]; then
        exit_reason="consec-fail $MAX_CONSEC_FAIL"; log "consecutive-failure limit — safe stop"; break
      fi
      ;;
    success)
      consec_fail=0
      HEAD_AFTER="$(git rev-parse HEAD 2>/dev/null || echo none)"
      if [ "$HEAD_AFTER" != "$HEAD_BEFORE" ]; then
        no_progress=0
        log "new commit: $(git log --oneline "$HEAD_BEFORE..$HEAD_AFTER" 2>/dev/null | tr '\n' ' ')"
      else
        no_progress=$((no_progress + 1))
        log "no-progress $no_progress/$MAX_NO_PROGRESS (no new commit)"
        if [ "$no_progress" -ge "$MAX_NO_PROGRESS" ]; then
          exit_reason="no-progress $MAX_NO_PROGRESS"; log "no-progress limit — safe stop"; break
        fi
      fi
      ;;
  esac

  if [ "$ONCE" -eq 1 ]; then
    exit_reason="--once complete"; log "--once — exit after one iteration"; break
  fi

  sleep "$PAUSE"
done

log "=== overnight loop end: $exit_reason (total $iter iters) ==="
emit_status "exit:$exit_reason" "$(git rev-parse HEAD 2>/dev/null || echo none)" ""

# Notify only on failure-class exits. drained / no-progress / MAX_ITER / manual STOP / --once are normal.
case "$exit_reason" in
  *"consec-fail"*|*"all-blocked"*) notify_failure "$exit_reason" ;;
esac
