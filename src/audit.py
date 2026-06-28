"""Persistent, append-only audit log for the gateway.

Audit events are emitted through the standard `mcp_audit` logger used across the
codebase (admin registrations, proxy calls, plugin executions, dashboard runs).
This module attaches a rotating JSON-lines file handler so those events survive
restarts, and exposes a reader for the `/v1/audit` endpoint.

Configuration:
  AUDIT_LOG_PATH  path of the audit file (default: ./data/audit.log)
"""

import json
import logging
import os
from logging.handlers import RotatingFileHandler

AUDIT_LOGGER_NAME = 'mcp_audit'

# Standard LogRecord attributes — anything else on a record is a custom field
# passed via `extra=` and belongs in the JSON payload.
_STD_ATTRS = set(vars(logging.makeLogRecord({})).keys()) | {'message', 'asctime', 'taskName'}


def audit_log_path() -> str:
    return os.environ.get('AUDIT_LOG_PATH', os.path.join('data', 'audit.log'))


class _JsonAuditFormatter(logging.Formatter):
    """Render each audit record as a single JSON line."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            'ts': self.formatTime(record, '%Y-%m-%dT%H:%M:%S%z'),
            'level': record.levelname,
            'event': record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _STD_ATTRS and not key.startswith('_'):
                payload[key] = value
        return json.dumps(payload, default=str, ensure_ascii=False)


def setup_audit_logging() -> logging.Logger:
    """Attach the rotating JSON file handler to the audit logger (idempotent)."""
    logger = logging.getLogger(AUDIT_LOGGER_NAME)
    logger.setLevel(logging.INFO)

    for handler in logger.handlers:
        if getattr(handler, '_mcp_audit', False):
            return logger  # already configured

    path = audit_log_path()
    try:
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        handler = RotatingFileHandler(path, maxBytes=5_000_000, backupCount=5, encoding='utf-8')
    except OSError as exc:
        # Read-only / unwritable path: keep the gateway running, audit stays
        # in-memory only (still emitted to the console via the root logger).
        logging.getLogger(__name__).warning(
            'audit log path %r is not writable (%s); persistence disabled', path, exc)
        return logger

    handler.setFormatter(_JsonAuditFormatter())
    handler._mcp_audit = True  # marker for idempotency
    logger.addHandler(handler)
    return logger


def read_audit(limit: int = 100) -> list[dict]:
    """Return the most recent audit entries (newest first)."""
    limit = max(1, min(limit, 1000))
    path = audit_log_path()
    if not os.path.exists(path):
        return []
    with open(path, 'r', encoding='utf-8') as fh:
        lines = fh.readlines()
    entries: list[dict] = []
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except Exception:
            entries.append({'raw': line})
        if len(entries) >= limit:
            break
    return entries
