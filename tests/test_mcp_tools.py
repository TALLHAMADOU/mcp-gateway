import asyncio
import pytest
from src import mcp_server


def _run(coro):
    return asyncio.run(coro)


# call_connector is the MCP proxy for `remote` connectors. We stub the
# connector registry so no servers.yaml entry or network call is needed.

def test_call_connector_unknown_raises(monkeypatch):
    monkeypatch.setattr(mcp_server, '_load_connectors', lambda: [])
    with pytest.raises(ValueError):
        _run(mcp_server.call_connector('nope'))


def test_call_connector_rejects_builtin(monkeypatch):
    monkeypatch.setattr(mcp_server, '_load_connectors',
                        lambda: [{'id': 'fs_local', 'type': 'builtin_fs'}])
    with pytest.raises(ValueError):
        _run(mcp_server.call_connector('fs_local'))


def test_call_connector_blocks_ssrf(monkeypatch):
    # remote connector resolving to loopback must be refused before any request
    monkeypatch.setattr(mcp_server, '_load_connectors',
                        lambda: [{'id': 'r', 'type': 'remote', 'url': 'http://127.0.0.1:9'}])
    with pytest.raises(ValueError):
        _run(mcp_server.call_connector('r', path='x'))
