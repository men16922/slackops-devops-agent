#!/usr/bin/env bash
# Root .env is the local source of truth for Vercel CLI credentials and the
# dashboard OAuth runtime configuration. Only runtime configuration is synced.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
# The linked Vercel project already has Root Directory=web. Deploy from the
# repository root so Vercel does not resolve it as web/web.
PROJECT_DIR="$REPO_ROOT"
ENV_FILE="$REPO_ROOT/.env"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "vercel-deploy: ERROR — missing $ENV_FILE" >&2
  exit 1
fi
if ! command -v vercel >/dev/null 2>&1; then
  echo "vercel-deploy: ERROR — Vercel CLI is required." >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

required=(
  VERCEL_TOKEN
  VERCEL_PROJECT_ID
  VERCEL_ORG_ID
  AUTH_GITHUB_ID
  AUTH_GITHUB_SECRET
  AUTH_SECRET
  GITHUB_ALLOWED_USERS
)
for name in "${required[@]}"; do
  if [[ -z "${!name:-}" ]]; then
    echo "vercel-deploy: ERROR — $name must be set in .env" >&2
    exit 1
  fi
done

common=(
  --cwd "$PROJECT_DIR"
  --token "$VERCEL_TOKEN"
  --scope "$VERCEL_ORG_ID"
)

echo "vercel-deploy: verifying project access"
vercel "${common[@]}" project inspect "$VERCEL_PROJECT_ID" >/dev/null

for name in AUTH_GITHUB_ID AUTH_GITHUB_SECRET AUTH_SECRET GITHUB_ALLOWED_USERS; do
  printf '%s\n' "${!name}" | vercel "${common[@]}" env add "$name" production --sensitive --force >/dev/null
  echo "vercel-deploy: synced $name to Production"
done

echo "vercel-deploy: deploying Production"
vercel "${common[@]}" deploy --prod --yes
