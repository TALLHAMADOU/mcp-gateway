from fastapi import Header, HTTPException
import os
import hmac

API_KEY = os.environ.get('MCP_GATEWAY_KEY')
if not API_KEY:
    # Fail fast to avoid running with a default or empty key
    raise RuntimeError('MCP_GATEWAY_KEY environment variable is not set')

async def require_api_key(authorization: str | None = Header(None)):
    # Accept either 'Bearer <key>' or raw key in header
    if not authorization:
        raise HTTPException(status_code=401, detail='Missing Authorization header')
    token = authorization
    if authorization.lower().startswith('bearer '):
        token = authorization.split(' ', 1)[1]
    # constant-time comparison to mitigate timing attacks
    if not hmac.compare_digest(token, API_KEY):
        raise HTTPException(status_code=403, detail='Invalid API key')
    return token
