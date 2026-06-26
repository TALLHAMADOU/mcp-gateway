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


def test_dashboard_execute_fs_lists_sandbox():
    # fs_local now runs the real handler: query '.' lists the sandbox root.
    r = client.post('/dashboard/execute', headers=AUTH,
                    json={'connector_id': 'fs_local', 'query': '.'})
    assert r.status_code == 200
    body = r.json()
    assert body['connector_id'] == 'fs_local'
    assert 'entries' in body['result']          # real result, not a mock
    assert 'duration_ms' in body


def test_dashboard_execute_fs_traversal_blocked():
    # The fs sandbox guard applies through the playground too.
    r = client.post('/dashboard/execute', headers=AUTH,
                    json={'connector_id': 'fs_local', 'query': '../../../../etc/passwd'})
    assert r.status_code == 200
    assert 'error' in r.json()


def test_dashboard_execute_unsupported_connector():
    # office needs a structured payload -> clear error, not a mock.
    r = client.post('/dashboard/execute', headers=AUTH,
                    json={'connector_id': 'office_local', 'query': 'x'})
    assert r.status_code == 200
    assert 'not supported' in r.json()['error']


def test_dashboard_execute_unknown_connector_404():
    r = client.post('/dashboard/execute', headers=AUTH,
                    json={'connector_id': 'nope', 'query': 'x'})
    assert r.status_code == 404


def test_dashboard_execute_missing_fields_400():
    r = client.post('/dashboard/execute', headers=AUTH, json={'connector_id': 'fs_local'})
    assert r.status_code == 400


def test_dashboard_history_records_executions():
    client.post('/dashboard/execute', headers=AUTH,
                json={'connector_id': 'fs_local', 'query': '.'})
    r = client.get('/dashboard/history', headers=AUTH)
    assert r.status_code == 200
    assert r.json()['count'] >= 1
