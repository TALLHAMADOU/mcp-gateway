from fastapi import Header, HTTPException
import os

API_KEY = os.environ.get('MCP_GATEWAY_KEY', 'sk_local_example')

async def require_api_key(authorization: str | None = Header(None)):
    # Accept either 'Bearer <key>' or raw key in header
    if not authorization:
        raise HTTPException(status_code=401, detail='Missing Authorization header')
    token = authorization
    if authorization.lower().startswith('bearer '):
        token = authorization.split(' ', 1)[1]
    if token != API_KEY:
        raise HTTPException(status_code=403, detail='Invalid API key')
    return token
