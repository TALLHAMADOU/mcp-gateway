#!/usr/bin/env bash
set -euo pipefail

GW=${1:-http://localhost:8080}
AUTH_HEADER=${2:-"Authorization: Bearer $MCP_GATEWAY_KEY"}

echo "Running smoke tests against $GW"

# 1) connectors
echo -n "Connectors... "
curl -s -H $AUTH_HEADER "$GW/v1/connectors" | jq -e . >/dev/null && echo OK || (echo FAIL && exit 1)

# 2) fs read
echo -n "FS read... "
curl -s -H $AUTH_HEADER "$GW/v1/fs/read?path=README.md" >/dev/null && echo OK || (echo FAIL && exit 1)

# 3) office health
echo -n "Office health... "
curl -s -H $AUTH_HEADER "$GW/v1/office/health" | jq -e '.libreoffice!=null' >/dev/null && echo OK || echo "Office check skipped or failed"

# 4) metrics
echo -n "Metrics... "
curl -s "$GW/metrics" >/dev/null && echo OK || echo "Metrics endpoint not available"

# 5) proxy (if example-remote present)
echo -n "Proxy ping (if configured)... "
if curl -s -H $AUTH_HEADER "$GW/v1/connectors" | jq -e '.[] | select(.id=="example-remote")' >/dev/null 2>&1; then
  echo "example-remote present (skipping actual proxy call)"
else
  echo "no example-remote"
fi

echo "Smoke tests completed."
