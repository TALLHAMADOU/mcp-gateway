import logging
from fastapi.testclient import TestClient
from src.main import app
from src import metrics, logging_config

client = TestClient(app)


# --- metrics ----------------------------------------------------------------

def test_metrics_response_is_prometheus_text():
    resp = metrics.metrics_response()
    assert metrics.CONTENT_TYPE_LATEST in resp.media_type
    assert b'mcp_requests_total' in resp.body


def test_metrics_counter_increment_is_exported():
    metrics.auth_failures.inc()
    assert b'mcp_auth_failures_total' in metrics.metrics_response().body


def test_metrics_endpoint_is_public():
    # /metrics must be scrapeable without the gateway key.
    r = client.get('/metrics')
    assert r.status_code == 200
    assert 'mcp_request_latency_seconds' in r.text


# --- logging_config ---------------------------------------------------------

def test_create_json_log_record_merges_fields():
    rec = logging_config.create_json_log_record(event='x', n=1)
    assert rec['event'] == 'x' and rec['n'] == 1 and 'timestamp' in rec


def test_setup_json_logging_disabled_is_noop():
    root = logging.getLogger()
    before = list(root.handlers)
    assert logging_config.setup_json_logging(enable_json=False) is None
    assert root.handlers == before


def test_setup_json_logging_enabled_adds_json_handler():
    from pythonjsonlogger import jsonlogger
    root = logging.getLogger()
    audit = logging.getLogger('mcp_audit')
    root_saved, audit_saved = list(root.handlers), list(audit.handlers)
    try:
        logging_config.setup_json_logging(enable_json=True)
        assert any(isinstance(h.formatter, jsonlogger.JsonFormatter)
                   for h in root.handlers)
    finally:
        # restore both loggers so other tests see the original handlers
        root.handlers[:] = root_saved
        audit.handlers[:] = audit_saved
