import os
from fastapi.testclient import TestClient
from src.main import app

KEY = os.environ['MCP_GATEWAY_KEY']
AUTH = {'Authorization': f'Bearer {KEY}'}
client = TestClient(app)


def test_tools_requires_auth():
    assert client.get('/v1/auto-discovery/tools').status_code == 401


def test_tools_lists_builtins_and_connectors():
    r = client.get('/v1/auto-discovery/tools', headers=AUTH)
    assert r.status_code == 200
    data = r.json()
    names = [t['name'] for t in data['tools']]
    assert 'fs_read' in names           # builtin
    assert data['count'] >= 4
    assert any(n.startswith('call_') for n in names)  # connectors


def test_registration_requires_auth():
    assert client.get('/v1/auto-discovery/registration').status_code == 401


def test_registration_script_generated():
    r = client.get('/v1/auto-discovery/registration', headers=AUTH)
    assert r.status_code == 200
    assert 'mcpServers' in r.json()['script']


def test_save_registration_claude_desktop():
    r = client.post('/v1/auto-discovery/register', headers=AUTH,
                    json={'client_type': 'claude-desktop', 'gateway_url': 'http://localhost:8080'})
    assert r.status_code == 200
    body = r.json()
    assert body['client_type'] == 'claude-desktop'
    assert 'gateway' in body['config']['mcpServers']


# --- health probes (no auth, used by k8s/LB) --------------------------------

def test_liveness_probe_open():
    r = client.get('/health/live')
    assert r.status_code == 200
    assert r.json()['alive'] is True


def test_health_check_open():
    r = client.get('/health')
    assert r.status_code == 200
    assert 'status' in r.json()
