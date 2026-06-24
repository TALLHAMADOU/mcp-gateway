Deployment notes for MCP Gateway (production)

Prerequisites
- Vault with secrets stored at secret/data/mcp-gateway (KV v2) or equivalent secret store.
- A Redis instance (recommended) for production rate-limiting (set REDIS_URL).
- TLS termination (nginx/Traefik) in front of the gateway.
- Docker runtime on host if using containerized LibreOffice (optional), and the gateway image must have access to the docker socket if container-runner is used.

Required environment variables (Vault-backed)
- MCP_GATEWAY_KEY: Primary API key for all clients (required).
- ADMIN_KEY: Admin key to enable /v1/admin/register (required to allow runtime connector registration).

Recommended environment variables
- REDIS_URL: redis://... (for distributed rate-limiting).
- POSTGRES_DSN / DATABASE_URL: Postgres connection (read-only role recommended).
- FS_ROOT: Root directory for filesystem sandbox.
- OFFICE_USE_CONTAINER=1: Enable containerized LibreOffice if you want conversions isolated.
- OFFICE_CONTAINER_IMAGE: Docker image for LibreOffice conversions (default: librewolf/libreoffice or your private build).
- OFFFICE_OUTPUT_DIR: Output dir (defaults to <FS_ROOT>/output)

Startup example (docker-compose.prod.yml)
- Ensure .env.production exists (fetched from Vault) and contains MCP_GATEWAY_KEY and ADMIN_KEY and REDIS_URL.
- docker compose -f docker-compose.prod.yml up -d --build

Security & hardening checklist
- Ensure MCP_GATEWAY_KEY and ADMIN_KEY are rotated and stored in Vault.
- Do not expose the Docker socket to untrusted workloads. If using container-runner, prefer running the container runner on a dedicated host or use a container runtime API with limited privileges.
- Configure TLS and HTTP security headers on the reverse proxy.
- Use an API gateway or WAF for additional rate-limiting and IP filtering.
- Ensure the Postgres user is read-only and limited by role/permissions.

Monitoring & observability
- Expose Prometheus metrics (add instrumentation) for:
  - auth failures
  - rate-limit hits
  - proxy errors
  - conversion errors
- Configure alerts for repeated auth failures or spike in 5xx errors.

CI / Security
- CI now includes pip-audit and bandit scans; fix any findings before production deploy.

Rollback & maintenance
- servers.yaml is updated atomically; keep backups of the file and consider using a GitOps approach for connector configuration.
- On deploy, verify health endpoints (/v1/office/health, /v1/docker/health) and run smoke tests.

Notes
- The in-memory rate-limiter is only suitable for single-instance deployments. For multi-instance, set REDIS_URL and ensure network connectivity to Redis.
- SSFR protections are in place but consider adding an explicit domain allowlist for known upstreams.
