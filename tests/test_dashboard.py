import os
from fastapi.testclient import TestClient
from src.main import app

KEY = os.environ['MCP_GATEWAY_KEY']
AUTH = {'Authorization': f'Bearer {KEY}'}
client = TestClient(app)


# --- the dashboard is now behind the gateway API key ------------------------

def test_dashboard_home_requires_auth():
    assert client.get('/dashboard/').status_code == 401


def test_dashboard_execute_requires_auth():
    r = client.post('/dashboard/execute', json={'connector_id': 'fs_local', 'query': 'x'})
    assert r.status_code == 401


def test_dashboard_home_ok():
    r = client.get('/dashboard/', headers=AUTH)
    assert r.status_code == 200
    assert 'text/html' in r.headers['content-type']


def test_dashboard_execute_ok():
    r = client.post('/dashboard/execute', headers=AUTH,
                    json={'connector_id': 'fs_local', 'query': 'ping'})
    assert r.status_code == 200
    assert r.json()['connector_id'] == 'fs_local'


def test_dashboard_execute_missing_fields_400():
    r = client.post('/dashboard/execute', headers=AUTH, json={'connector_id': 'fs_local'})
    assert r.status_code == 400
