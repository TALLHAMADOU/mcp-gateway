import os
import tempfile

# Must be set before `src.auth` / `src.handlers.fs` are imported, since both
# read their config at module import time.
os.environ.setdefault('MCP_GATEWAY_KEY', 'sk_test_key')
os.environ.setdefault('FS_ROOT', os.getcwd())
# Keep the persistent audit log out of the repo tree during tests.
os.environ.setdefault('AUDIT_LOG_PATH', os.path.join(tempfile.gettempdir(), 'mcp_gateway_test_audit.log'))
