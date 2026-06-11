#!/usr/bin/env bash
# overnight runner — NEXT_PLAN [auto] 백로그를 headless 회차로 자율 진행.
# 사용:
#   caffeinate -dimsu bin/overnight/run.sh &     # 무인 가동 (tmux 권장)
#   bin/overnight/run.sh --once                  # 1회차만 (검증용)
#   touch bin/overnight/STOP                     # 중단 요청
# 설계: 회차마다 fresh context 로 /sync → 작업 1묶음 → /checkpoint → commit.
#       usage limit 도달 시 LIMIT_WAIT 대기 후 재시도(리셋 후 속행).
# 결과 분류: claude -p --output-format json 의 마지막 JSON 객체 is_error 로 성공을 먼저
#   판정한다. 성공(is_error=false)이면 result 텍스트에 'rate limit' 등이 언급돼도 무시한다
#   (정상 회차 오판 방지). 성공이 아닐 때만 limit 텍스트를 검사해 wait/retry 로 분기한다.
set -u

DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$DIR/../.." && pwd)"
LOG_DIR="$DIR/logs"
RUNNER_LOG="$LOG_DIR/runner.log"
STOP_FILE="$DIR/STOP"
DONE_FILE="$DIR/DONE"

MAX_ITER="${MAX_ITER:-50}"            # 폭주 방지 백스톱
ITER_TIMEOUT="${ITER_TIMEOUT:-3600}"  # 회차당 최대 초
LIMIT_WAIT="${LIMIT_WAIT:-1800}"      # limit 감지 시 대기 초
PAUSE="${PAUSE:-30}"                  # 회차 간 간격 초
MAX_CONSEC_FAIL="${MAX_CONSEC_FAIL:-3}"

mkdir -p "$LOG_DIR"
cd "$REPO_ROOT"

note() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$RUNNER_LOG"; }

once=false
[ "${1:-}" = "--once" ] && once=true

# macOS 기본 timeout 부재 대비
run_with_timeout() {
  if command -v timeout >/dev/null 2>&1; then
    timeout "$ITER_TIMEOUT" "$@"
  elif command -v gtimeout >/dev/null 2>&1; then
    gtimeout "$ITER_TIMEOUT" "$@"
  else
    "$@"  # timeout 미가용 — 회차 자체에 의존
  fi
}

# 회차 로그 + rc 로부터 결과 분류: success / limit / failure.
# 성공은 --output-format json 의 is_error=false 로 판정(가장 신뢰 가능한 신호).
# 성공이 아닐 때만 limit 텍스트를 검사 → 정상 회차의 'rate limit' 언급 오판을 막는다.
classify_outcome() {
  python3 - "$1" "$2" <<'PY'
import json, re, sys

text = open(sys.argv[1], encoding="utf-8", errors="replace").read()
rc = int(sys.argv[2])

def payload(t):
    t = t.strip()
    if not t:
        return None
    for cand in (t.splitlines()[-1], t):
        try:
            obj = json.loads(cand)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(obj, dict):
            return obj
    return None

obj = payload(text)
if isinstance(obj, dict) and obj.get("is_error") is False:
    print("success")
elif re.search(
    r"usage limit|session limit|rate.?limit|limit (reached|exceeded)|hit your.*limit|overloaded",
    text, re.IGNORECASE,
):
    print("limit")
else:
    print("failure" if rc != 0 else "success")
PY
}

note "runner start (max_iter=$MAX_ITER once=$once repo=$REPO_ROOT)"
iter=0
consec_fail=0

while [ "$iter" -lt "$MAX_ITER" ]; do
  if [ -f "$STOP_FILE" ]; then note "STOP file detected — exiting"; break; fi
  if [ -f "$DONE_FILE" ]; then note "DONE file detected — backlog exhausted, exiting"; break; fi

  iter=$((iter + 1))
  ITER_LOG="$LOG_DIR/iter-$(date '+%Y%m%d-%H%M%S').log"
  note "iter $iter start → $ITER_LOG"

  run_with_timeout claude -p "$(cat "$DIR/PROMPT.md")" \
    --permission-mode acceptEdits \
    --output-format json \
    >"$ITER_LOG" 2>&1
  rc=$?

  outcome="$(classify_outcome "$ITER_LOG" "$rc")"

  if [ "$outcome" = "limit" ]; then
    note "iter $iter: usage/session limit detected (rc=$rc) — sleeping ${LIMIT_WAIT}s"
    consec_fail=0
    $once && { note "once mode — exiting after limit"; break; }
    sleep "$LIMIT_WAIT"
    continue
  fi

  if [ "$outcome" = "failure" ]; then
    consec_fail=$((consec_fail + 1))
    note "iter $iter: FAILED rc=$rc (consecutive=$consec_fail)"
    if [ "$consec_fail" -ge "$MAX_CONSEC_FAIL" ]; then
      note "aborting after $consec_fail consecutive failures — inspect $LOG_DIR"
      break
    fi
  else
    consec_fail=0
    note "iter $iter: ok (commit=$(git -C "$REPO_ROOT" log --oneline -1 2>/dev/null | head -1))"
  fi

  $once && { note "once mode — exiting after single iteration"; break; }
  sleep "$PAUSE"
done

note "runner end (iterations=$iter)"
