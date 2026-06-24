"""JSON logging configuration for structured output."""

import logging
import json
import os
from datetime import datetime
from pythonjsonlogger import jsonlogger


def setup_json_logging(enable_json: bool = None):
    """
    Configure JSON logging if LOG_JSON environment variable is set.
    
    Args:
        enable_json: If True, enable JSON logging. If None, check LOG_JSON env var.
    """
    if enable_json is None:
        enable_json = os.environ.get('LOG_JSON', 'false').lower() == 'true'
    
    if not enable_json:
        return
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Add JSON handler
    handler = logging.StreamHandler()
    formatter = jsonlogger.JsonFormatter(
        '%(timestamp)s %(level)s %(name)s %(message)s',
        timestamp=True
    )
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)
    
    # Also log audit events as JSON
    audit_logger = logging.getLogger('mcp_audit')
    audit_logger.setLevel(logging.INFO)
    audit_logger.addHandler(handler)


def create_json_log_record(**kwargs):
    """
    Create a structured log record (for manual use).
    
    Args:
        **kwargs: Fields to include in the log record
    
    Returns:
        dict with timestamp and merged kwargs
    """
    record = {
        "timestamp": datetime.utcnow().isoformat(),
        **kwargs
    }
    return record
