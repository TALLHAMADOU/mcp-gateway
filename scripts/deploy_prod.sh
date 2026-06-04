#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"

if ! command -v vault >/dev/null 2>&1; then
  echo "vault CLI not found. Install and authenticate before running this script."
  exit 1
fi
if ! command -v jq >/dev/null 2>&1; then
  echo "jq required. Install jq."
  exit 1
fi

VAULT_PATH=${VAULT_PATH:-secret/mcp-gateway}

echo "Fetching secrets from Vault path: $VAULT_PATH"
vault kv get -format=json "$VAULT_PATH" | jq -r '.data.data | to_entries[] | "\(.key)=\(.value)"' > .env.production

echo ".env.production created (ensure it's in .gitignore)."

echo "Starting services via docker-compose.prod.yml"
docker-compose -f docker-compose.prod.yml up -d --build

echo "Done."
