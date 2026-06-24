Summary of changes for PR: prod hardening and security

This PR contains a set of security and production hardening changes to the MCP Gateway. High-level summary:

- Auth hardening
  - Require MCP_GATEWAY_KEY environment variable (fail-fast) and use constant-time comparisons for token checks.

- Admin & configuration
  - POST /v1/admin/register now requires ADMIN_KEY to be configured; registration is disabled otherwise.
  - servers.yaml updates are atomic (tempfile + os.replace).
  - Remote connector URLs must use https:// and are validated to prevent SSRF (no private/loopback addresses).
  - Audit logging added for admin registrations and proxy requests (mcp_audit logger).

- Proxy & SSRF protections
  - Upstream URLs are validated (DNS resolution) and rejected if they resolve to private/loopback/link-local/reserved addresses.

- Docker handler
  - docker inspection results are sanitized to remove Env and HostConfig to prevent leaking container secrets.

- SQL guard
  - Use sqlparse when available for robust single-statement/type checks; fallback to improved heuristics.

- Rate limiting
  - New RateLimitMiddleware supports Redis-backed fixed-window limiting when REDIS_URL is configured, with an in-memory token-bucket fallback for local/dev.

- Office isolation
  - Optional containerized LibreOffice runner (OFFICE_USE_CONTAINER=1) to isolate conversions in a short-lived docker container (network disabled, least privileges).

- CI / Security Scans
  - CI now runs pip-audit and bandit (reports) as part of the workflow.

- Tests
  - Existing tests pass locally (31 passed). New targeted tests added for SSRF, docker sanitization and rate-limiting behavior.

Files added/changed (highlights)
- src/auth.py (hardening)
- src/mcp_server.py (hmac compare)
- src/main.py (SSRF checks, atomic writes, audit logs, middleware attachment)
- src/handlers/docker_handler.py (sanitization)
- src/sql_guard.py (sqlparse support)
- src/middleware.py (redis-aware rate limiter)
- src/handlers/container_runner.py (optional container runner)
- src/handlers/office.py (opt-in container use)
- .github/workflows/ci.yml (pip-audit, bandit)
- README.md (security notes)
- requirements.txt (sqlparse, redis)

Security considerations & follow-ups
- Ensure MCP_GATEWAY_KEY and ADMIN_KEY are provisioned via Vault and not committed.
- Set REDIS_URL in production for distributed rate limiting.
- Consider enforcing an allowlist/denylist for upstream domains beyond IP checks.
- Monitor bandit/pip-audit outputs and remediate any flagged issues.

Testing notes
- Tests executed in a virtualenv: 31 passed, 265 warnings.

Please review and let me know if you'd like smaller incremental PRs (e.g. auth-only, middleware-only).
