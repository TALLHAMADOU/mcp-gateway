import os
import json
import logging
from fastapi.testclient import TestClient
from src.main import app
from src import audit

KEY = os.environ['MCP_GATEWAY_KEY']
AUTH = {'Authorization': f'Bearer {KEY}'}
client = TestClient(app)


# --- module: events are written as JSON lines and read back newest-first -----

def test_setup_is_idempotent():
    audit.setup_audit_logging()
    before = len(logging.getLogger(audit.AUDIT_LOGGER_NAME).handlers)
    audit.setup_audit_logging()
    after = len(logging.getLogger(audit.AUDIT_LOGGER_NAME).handlers)
    assert before == after


def test_event_is_persisted_and_parsed():
    logger = audit.setup_audit_logging()
    logger.info('test.event', extra={'connector_id': 'abc', 'status': 'ok'})
    for h in logger.handlers:
        h.flush()
    entries = audit.read_audit(limit=50)
    match = next((e for e in entries if e.get('event') == 'test.event'), None)
    assert match is not None
    assert match['connector_id'] == 'abc'
    assert match['status'] == 'ok'

    # the file really holds valid JSON lines
    with open(audit.audit_log_path(), 'r', encoding='utf-8') as fh:
        last = [l for l in fh.read().splitlines() if l.strip()][-1]
    assert json.loads(last)['event']


# --- HTTP: /v1/audit is admin-gated ------------------------------------------

def test_audit_endpoint_requires_admin_config(monkeypatch):
    import src.main as m
    monkeypatch.setattr(m, 'ADMIN_KEY', None)
    r = client.get('/v1/audit', headers=AUTH)
    assert r.status_code == 403


def test_audit_endpoint_rejects_bad_admin_key(monkeypatch):
    import src.main as m
    monkeypatch.setattr(m, 'ADMIN_KEY', 'admin-secret')
    r = client.get('/v1/audit', headers={**AUTH, 'X-Admin-Key': 'wrong'})
    assert r.status_code == 403


def test_audit_endpoint_returns_entries(monkeypatch):
    import src.main as m
    monkeypatch.setattr(m, 'ADMIN_KEY', 'admin-secret')
    audit.setup_audit_logging().info('http.test', extra={'k': 'v'})
    r = client.get('/v1/audit', headers={**AUTH, 'X-Admin-Key': 'admin-secret'})
    assert r.status_code == 200
    body = r.json()
    assert body['count'] >= 1
    assert 'entries' in body


def test_audit_endpoint_requires_auth():
    assert client.get('/v1/audit').status_code == 401
