#!/usr/bin/env bash
set -e
export MCP_GATEWAY_KEY=${MCP_GATEWAY_KEY:-sk_local_example}
uvicorn src.main:app --reload --host 0.0.0.0 --port 8080
