import os
from fastapi.testclient import TestClient
from src.main import app

KEY = os.environ['MCP_GATEWAY_KEY']
AUTH = {'Authorization': f'Bearer {KEY}'}
client = TestClient(app)


# --- auth on the top-level routes -------------------------------------------

def test_connectors_requires_auth():
    assert client.get('/v1/connectors').status_code == 401


def test_connectors_rejects_wrong_key():
    r = client.get('/v1/connectors', headers={'Authorization': 'Bearer nope'})
    assert r.status_code == 403


def test_connectors_ok_with_key():
    r = client.get('/v1/connectors', headers=AUTH)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


# --- auth now also covers builtin handlers (regression for the bypass) ------

def test_builtin_handler_requires_auth():
    assert client.get('/v1/fs/list').status_code == 401
    assert client.get('/v1/docker/health').status_code == 401


# --- filesystem sandbox containment -----------------------------------------

def test_fs_blocks_absolute_path():
    r = client.get('/v1/fs/read', params={'path': '/etc/passwd'}, headers=AUTH)
    assert r.status_code == 403


def test_fs_blocks_traversal():
    r = client.get('/v1/fs/read',
                   params={'path': '../../../../etc/passwd'}, headers=AUTH)
    assert r.status_code == 403


def test_fs_list_inside_sandbox_ok():
    r = client.get('/v1/fs/list', params={'path': '.'}, headers=AUTH)
    assert r.status_code == 200
    assert 'entries' in r.json()
