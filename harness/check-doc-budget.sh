#!/usr/bin/env bash
# Enforce context-budget line caps on the entry docs (loaded every session/overnight iteration).
# Caps mirror .claude/harness-config.json budgets. Over cap → fail with a /tidy-docs hint.
set -euo pipefail
cd "$(dirname "$0")/.."
fail=0
check() { # path cap
  if [ ! -f "$1" ]; then echo "doc-budget: MISSING $1"; fail=1; return; fi
  local n; n=$(wc -l < "$1" | tr -d ' ')
  if [ "$n" -gt "$2" ]; then echo "doc-budget: OVER  $1 = ${n} (cap $2) — run /tidy-docs"; fail=1
  else echo "doc-budget: ok    $1 = ${n}/$2"; fi
}
check docs/AGENT_BRIEF.md   60
check docs/STATUS.md       120
check docs/NEXT_PLAN.md    120
check docs/PROGRESS_LOG.md 120
[ "$fail" -eq 0 ] && echo "doc-budget: OK" || { echo "doc-budget: FAIL"; exit 1; }
