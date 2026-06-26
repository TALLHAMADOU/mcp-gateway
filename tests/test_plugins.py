import os
from fastapi.testclient import TestClient
from src.main import app
from src import plugin_registry

KEY = os.environ['MCP_GATEWAY_KEY']
AUTH = {'Authorization': f'Bearer {KEY}'}
client = TestClient(app)


def _ensure_loaded():
    plugin_registry.load_plugins()


# --- registry layer ---------------------------------------------------------

def test_load_registers_example_tools():
    _ensure_loaded()
    plugins = plugin_registry.list_plugins()
    assert 'example_math_add' in plugins
    assert plugins['example_math_add']['inputSchema']['required'] == ['a', 'b']


def test_input_schema_optional_arg_not_required():
    _ensure_loaded()
    weather = plugin_registry.list_plugins()['example_weather_weather']
    # `unit` has a default -> optional; `city` is required
    assert 'city' in weather['inputSchema']['required']
    assert 'unit' not in weather['inputSchema']['required']


# --- HTTP layer -------------------------------------------------------------

def test_list_plugins_requires_auth():
    assert client.get('/v1/plugins').status_code == 401


def test_list_plugins_ok():
    _ensure_loaded()
    r = client.get('/v1/plugins', headers=AUTH)
    assert r.status_code == 200
    assert r.json()['count'] >= 1


def test_execute_plugin_add():
    _ensure_loaded()
    r = client.post('/v1/plugins/example_math_add/execute', headers=AUTH,
                    json={'a': 2, 'b': 3})
    assert r.status_code == 200
    assert r.json()['result'] == 5


def test_execute_unknown_plugin_404():
    r = client.post('/v1/plugins/does_not_exist/execute', headers=AUTH, json={})
    assert r.status_code == 404


def test_execute_plugin_bad_args_400():
    _ensure_loaded()
    r = client.post('/v1/plugins/example_math_add/execute', headers=AUTH,
                    json={'a': 1})  # missing b
    assert r.status_code == 400


def test_delete_plugin_blocked_without_admin_key(monkeypatch):
    _ensure_loaded()
    import src.main as m
    monkeypatch.setattr(m, 'ADMIN_KEY', None)
    r = client.delete('/v1/plugins/example_math_add', headers=AUTH)
    assert r.status_code == 403


def test_delete_plugin_with_admin_key(monkeypatch):
    _ensure_loaded()
    import src.main as m
    monkeypatch.setattr(m, 'ADMIN_KEY', 'admin-secret')
    r = client.delete('/v1/plugins/example_math_add',
                      headers={**AUTH, 'X-Admin-Key': 'admin-secret'})
    assert r.status_code == 200
    plugin_registry.load_plugins()  # restore for other tests
