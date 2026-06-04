MCP Gateway - Python FastAPI MVP

Quick start:
- python3 -m venv .venv && source .venv/bin/activate
- pip install -r requirements.txt
- export MCP_GATEWAY_KEY=sk_local_example
- ./scripts/dev.sh

Endpoints:
- GET /v1/connectors (Auth)
- POST /v1/admin/register (Auth)
- Proxy: /v1/proxy/{connector_id}/{path}
- Builtin FS: /v1/fs/list, /v1/fs/read
- PostgreSQL: /v1/postgres/health, /v1/postgres/query (POST)

PostgreSQL usage (MVP - read-only)
- Configure connection via env:
  export POSTGRES_DSN="postgres://user:pass@localhost:5432/dbname"
  or set DATABASE_URL
- Example query (only SELECT allowed):
  curl -H "Authorization: Bearer sk_local_example" -H "Content-Type: application/json" \
    -d '{"sql":"SELECT id, name FROM users LIMIT 5"}' \
    http://localhost:8080/v1/postgres/query
- Alternatively provide dsn in payload (less secure):
  {
    "dsn": "postgres://user:pass@host/db",
    "sql": "SELECT * FROM table LIMIT 10"
  }

Connection pooling & limits (added):
- Pooling: uses psycopg2 ThreadedConnectionPool. Configure with env vars:
  export PG_MIN_CONN=1
  export PG_MAX_CONN=5
- Timeouts & row limits:
  export PG_STATEMENT_TIMEOUT_MS=5000   # per-query statement_timeout (ms)
  export PG_MAX_ROWS=1000               # maximum rows returned (post-truncation)
- These protect the gateway from long queries and high DB load. For heavy production use, place a real pooler (pgbouncer) and enforce roles.

Security notes:
- MVP only allows SELECT to avoid accidental writes. For production, add RBAC, query auditing, and connection separation for readonly roles.

CLI usage example:
curl -H "Authorization: Bearer sk_local_example" http://localhost:8080/v1/connectors
