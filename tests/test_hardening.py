import os
from fastapi import FastAPI
from fastapi.testclient import TestClient
from src.main import app
from src.middleware import RateLimitMiddleware
from src.auto_discovery import generate_mcp_registration_script

KEY = os.environ['MCP_GATEWAY_KEY']
AUTH = {'Authorization': f'Bearer {KEY}'}
client = TestClient(app)


# --- #7: docs / openapi are no longer public ---------------------------------

def test_openapi_requires_auth():
    assert client.get('/openapi.json').status_code == 401


def test_docs_requires_auth():
    assert client.get('/docs').status_code == 401


def test_openapi_ok_with_key():
    r = client.get('/openapi.json', headers=AUTH)
    assert r.status_code == 200
    assert r.json()['info']['title'] == 'MCP Gateway'


def test_docs_ok_with_key():
    r = client.get('/docs', headers=AUTH)
    assert r.status_code == 200
    assert 'text/html' in r.headers['content-type']


# --- #8: 429 carries a Retry-After header ------------------------------------

def test_rate_limit_sets_retry_after():
    mini = FastAPI()
    mini.add_middleware(RateLimitMiddleware, calls_per_minute=1, burst=1)

    @mini.get('/ping')
    async def ping():
        return {'ok': True}

    c = TestClient(mini)
    # First request consumes the only token; the second is throttled.
    assert c.get('/ping', headers={'Authorization': 'Bearer a'}).status_code == 200
    r = c.get('/ping', headers={'Authorization': 'Bearer a'})
    assert r.status_code == 429
    assert int(r.headers['Retry-After']) >= 1


# --- #9: registration defaults point at the real port (8080) -----------------

def test_registration_script_uses_8080():
    script = generate_mcp_registration_script(api_key='sk_testkey')
    assert 'localhost:8080' in script
    assert 'localhost:8000' not in script
