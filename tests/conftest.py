import os

# Must be set before `src.auth` / `src.handlers.fs` are imported, since both
# read their config at module import time.
os.environ.setdefault('MCP_GATEWAY_KEY', 'sk_test_key')
os.environ.setdefault('FS_ROOT', os.getcwd())
