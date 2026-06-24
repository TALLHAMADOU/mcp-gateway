import os
import time
import pytest
from fastapi.testclient import TestClient
from src.main import app

KEY = os.environ['MCP_GATEWAY_KEY']
AUTH = {'Authorization': f'Bearer {KEY}'}
client = TestClient(app)


def test_docker_inspect_sanitizes():
    from src.handlers.docker_handler import _sanitize_container
    attrs = {
        'Config': {'Env': ['SECRET=top'], 'Other': 1},
        'HostConfig': {'Binds': ['/etc/passwd:/etc/passwd']},
        'Id': 'abcd',
    }
    out = _sanitize_container(attrs)
    assert 'HostConfig' not in out
    assert 'Config' in out
    assert 'Env' not in out['Config']


def test_admin_register_rejects_private_url(monkeypatch):
    # Make ADMIN_KEY equal to API key so the same Authorization header satisfies both
    monkeypatch.setenv('ADMIN_KEY', KEY)
    payload = {'id': 'tmp-1', 'type': 'remote', 'url': 'https://127.0.0.1/some'}
    headers = {**AUTH, 'X-Admin-Key': KEY}
    r = client.post('/v1/admin/register', headers=headers, json=payload)
    assert r.status_code == 403


def test_rate_limiter_inmemory_small_window():
    # Create a small app using the same middleware but with a very small limit
    from fastapi import FastAPI
    from src.middleware import RateLimitMiddleware
    from fastapi.testclient import TestClient

    app2 = FastAPI()
    app2.add_middleware(RateLimitMiddleware, calls_per_minute=2, burst=2)

    @app2.get('/ping')
    def ping():
        return {'ok': True}

    c = TestClient(app2)
    r1 = c.get('/ping')
    r2 = c.get('/ping')
    r3 = c.get('/ping')
    # first two should be OK, third should be limited
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r3.status_code == 429
