import os
import pytest
from fastapi.testclient import TestClient
from src.main import app
from src import auth

client = TestClient(app)


@pytest.fixture
def plugins_only_key(monkeypatch):
    # A key scoped to /v1/plugins/* only.
    monkeypatch.setitem(auth._KEYS, 'sk_plugins_only', frozenset({'plugins'}))
    return 'sk_plugins_only'


def test_scoped_key_allowed_inside_scope(plugins_only_key):
    r = client.get('/v1/plugins', headers={'Authorization': f'Bearer {plugins_only_key}'})
    assert r.status_code == 200


def test_scoped_key_denied_outside_scope(plugins_only_key):
    r = client.get('/v1/connectors', headers={'Authorization': f'Bearer {plugins_only_key}'})
    assert r.status_code == 403
    assert 'scope' in r.json()['detail']


def test_full_access_key_reaches_everything():
    h = {'Authorization': f"Bearer {os.environ['MCP_GATEWAY_KEY']}"}
    assert client.get('/v1/plugins', headers=h).status_code == 200
    assert client.get('/v1/connectors', headers=h).status_code == 200


def test_unknown_key_is_rejected():
    assert client.get('/v1/plugins', headers={'Authorization': 'Bearer nope'}).status_code == 403


def test_missing_header_is_401():
    assert client.get('/v1/plugins').status_code == 401


# --- registry parsing -------------------------------------------------------

def test_parse_keys_merges_single_and_json(monkeypatch):
    monkeypatch.setenv('MCP_GATEWAY_KEY', 'sk_main')
    monkeypatch.setenv('MCP_GATEWAY_KEYS', '{"sk_a": ["fs", "github"], "sk_b": "*"}')
    keys = auth._parse_keys()
    assert keys['sk_main'] == frozenset({'*'})
    assert keys['sk_a'] == frozenset({'fs', 'github'})
    assert keys['sk_b'] == frozenset({'*'})


def test_parse_keys_rejects_bad_json(monkeypatch):
    monkeypatch.setenv('MCP_GATEWAY_KEYS', 'not-json')
    with pytest.raises(RuntimeError):
        auth._parse_keys()
