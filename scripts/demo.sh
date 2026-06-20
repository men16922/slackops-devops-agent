#!/usr/bin/env bash
#
# demo.sh — 로컬 데모 풀스택을 한 번에 띄운다(`make demo`).
# ----------------------------------------------------------------------------
# web/docker-compose 는 web + dynamodb-local + seed 만 띄운다 — 대화/job 을 소비할
# 호스트 poller(chat_agent / worker)가 없으면 채팅은 status=awaiting_agent 에 갇혀
# "에이전트 응답 중…" 에서 멈춘다(worker 미가동 시 job 이 pending 에 멈추는 것과 동일).
#
# 이 스크립트는 docker compose(web+DB+seed) + chat_agent + worker 를 함께 띄우고,
# 종료(Ctrl-C) 시 poller 와 docker 스택을 전부 정리한다.
# env(DDB_ENDPOINT/AWS 더미키)는 Makefile 의 DEV_ENV 와 동일하게 맞춘다.
#
#   export CLAUDE_CODE_OAUTH_TOKEN="$(claude setup-token)"   # 실 Claude 응답에 필요
#   make demo
# ----------------------------------------------------------------------------
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# 로컬 편의: .env 가 있으면 자동 로드(SLACK/CLAUDE 토큰 등). gitignored + 로컬 전용 —
# EC2 는 demo.sh 를 쓰지 않고 SSM→/etc/...env 파일을 쓰므로 영향 없음.
if [ -f .env ]; then
  set -a; . ./.env; set +a
fi

if [ -z "${CLAUDE_CODE_OAUTH_TOKEN:-}" ]; then
  echo "demo: ERROR — CLAUDE_CODE_OAUTH_TOKEN 미설정. 실 Claude 응답에 필요하다." >&2
  echo "  export CLAUDE_CODE_OAUTH_TOKEN=\"\$(claude setup-token)\" 후 다시 실행." >&2
  exit 1
fi

# Makefile DEV_ENV 와 동일 — 호스트 poller 가 compose 의 dynamodb-local(8931)에 붙는다.
export PYTHONPATH=src
export DDB_ENDPOINT="${DDB_ENDPOINT:-http://localhost:8931}"
export AWS_REGION="${AWS_REGION:-us-east-1}"
export AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID:-local}"
export AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY:-local}"

pids=()
cleanup() {
  echo ""
  echo "demo: 정리 중 — poller 종료 + docker compose down…"
  for pid in "${pids[@]:-}"; do kill "$pid" 2>/dev/null || true; done
  ( cd web && docker compose down ) || true
}
trap cleanup INT TERM EXIT

echo "demo: docker compose up — web + dynamodb-local + seed…"
( cd web && docker compose up -d )

echo "demo: 호스트 poller 기동 — chat_agent(대화 응답) + worker(승인 job 실행)…"
python3 -m app.chat_agent & pids+=($!)
python3 -m app.worker      & pids+=($!)

echo "demo: ready → http://localhost:8930   (Ctrl-C 로 전체 종료)"
wait
