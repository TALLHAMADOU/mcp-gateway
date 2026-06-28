"""API-key authentication with per-key scopes (lightweight RBAC).

Two configuration sources, merged:

  MCP_GATEWAY_KEY   single key, granted full access ('*'). Backward compatible.
  MCP_GATEWAY_KEYS  JSON object mapping key -> scopes, e.g.
                      {"sk_reader": ["fs", "github"], "sk_admin": ["*"]}
                    scopes may also be a comma string ("fs,github").

A *scope* is the path segment after ``/v1/`` (fs, github, postgres, plugins,
connectors, proxy, admin, audit, auto-discovery, ...) or ``dashboard``. The
scope ``*`` grants access to everything. Keys never auto-expand: a key scoped
``["fs"]`` gets 403 on ``/v1/github/*``.
"""
from fastapi import Header, HTTPException, Request
import os
import re
import json
import hmac


def _parse_keys() -> dict:
    """Build the {api_key: frozenset(scopes)} registry from the environment."""
    keys: dict = {}

    single = os.environ.get('MCP_GATEWAY_KEY')
    if single:
        keys[single] = frozenset({'*'})

    raw = os.environ.get('MCP_GATEWAY_KEYS')
    if raw:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f'MCP_GATEWAY_KEYS is not valid JSON: {exc}')
        if not isinstance(data, dict):
            raise RuntimeError('MCP_GATEWAY_KEYS must be a JSON object {key: [scopes]}')
        for key, scopes in data.items():
            if isinstance(scopes, str):
                scopes = [s.strip() for s in scopes.split(',') if s.strip()]
            keys[key] = frozenset(scopes or {'*'})

    return keys


_KEYS = _parse_keys()
if not _KEYS:
    # Fail fast to avoid running with a default or empty key.
    raise RuntimeError('No API keys configured: set MCP_GATEWAY_KEY or MCP_GATEWAY_KEYS')

# Primary key, kept for components that still authenticate with a single key
# (e.g. the /mcp ASGI guard).
API_KEY = os.environ.get('MCP_GATEWAY_KEY') or next(iter(_KEYS))


def _match_key(token: str):
    """Return the scopes granted to `token`, or None. Constant-time over keys."""
    matched = None
    for key, scopes in _KEYS.items():
        if hmac.compare_digest(token, key):
            matched = scopes
    return matched


def _required_scope(path: str):
    """Map a request path to the scope it requires (None = unscoped)."""
    m = re.match(r'/v1/([^/]+)', path)
    if m:
        return m.group(1)
    if path.startswith('/dashboard'):
        return 'dashboard'
    return None


async def require_api_key(request: Request, authorization: str | None = Header(None)):
    # Accept either 'Bearer <key>' or a raw key in the header.
    if not authorization:
        raise HTTPException(status_code=401, detail='Missing Authorization header')
    token = authorization
    if authorization.lower().startswith('bearer '):
        token = authorization.split(' ', 1)[1]

    scopes = _match_key(token)
    if scopes is None:
        raise HTTPException(status_code=403, detail='Invalid API key')

    required = _required_scope(request.url.path)
    if required and '*' not in scopes and required not in scopes:
        raise HTTPException(status_code=403, detail=f"API key lacks scope '{required}'")

    return token
