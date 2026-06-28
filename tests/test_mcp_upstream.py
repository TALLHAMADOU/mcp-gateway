import asyncio
import textwrap

import pytest

pytest.importorskip("mcp")  # the bridge module imports the MCP SDK at import time
from src import mcp_upstream  # noqa: E402


# --- config parsing + ${VAR} expansion --------------------------------------

def test_expand_fills_env_placeholders(monkeypatch):
    monkeypatch.setenv("TOK", "secret123")
    cfg = {"headers": {"Authorization": "Bearer ${TOK}"}, "args": ["${TOK}", "plain"]}
    out = mcp_upstream._expand(cfg)
    assert out["headers"]["Authorization"] == "Bearer secret123"
    assert out["args"] == ["secret123", "plain"]


def test_expand_unknown_var_becomes_empty(monkeypatch):
    monkeypatch.delenv("NOPE", raising=False)
    assert mcp_upstream._expand("x-${NOPE}-y") == "x--y"


def test_load_config_missing_file_returns_empty(monkeypatch, tmp_path):
    monkeypatch.setenv("MCP_SERVERS_CONFIG", str(tmp_path / "absent.yaml"))
    assert mcp_upstream._load_config() == {}


def test_load_config_reads_and_expands(monkeypatch, tmp_path):
    monkeypatch.setenv("COMPANY_TOKEN", "abc")
    path = tmp_path / "mcp_servers.yaml"
    path.write_text(textwrap.dedent("""
        mcp_servers:
          company:
            transport: http
            url: https://mcp.example.com/mcp
            headers:
              Authorization: "Bearer ${COMPANY_TOKEN}"
    """))
    monkeypatch.setenv("MCP_SERVERS_CONFIG", str(path))
    cfg = mcp_upstream._load_config()
    assert cfg["company"]["headers"]["Authorization"] == "Bearer abc"


def test_stdio_disabled_by_default(monkeypatch):
    monkeypatch.delenv("MCP_UPSTREAM_ENABLE_STDIO", raising=False)
    assert mcp_upstream._stdio_enabled() is False
    monkeypatch.setenv("MCP_UPSTREAM_ENABLE_STDIO", "1")
    assert mcp_upstream._stdio_enabled() is True


# --- generic bridge tools (call/list) with a fake upstream session ----------

class _Text:
    type = "text"

    def __init__(self, text):
        self.text = text


class _Result:
    def __init__(self, content, is_error=False):
        self.content = content
        self.isError = is_error


class _Tool:
    def __init__(self, name):
        self.name = name
        self.description = f"desc {name}"
        self.inputSchema = {"type": "object", "properties": {}}


class _FakeSession:
    def __init__(self, result):
        self._result = result
        self.calls = []

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        return self._result


@pytest.fixture(autouse=True)
def _clean_registry():
    mcp_upstream._registry.clear()
    yield
    mcp_upstream._registry.clear()


def test_list_reports_tools_with_schema():
    mcp_upstream._registry["srv"] = {
        "session": _FakeSession(_Result([])),
        "tools": [_Tool("read_file"), _Tool("write_file")],
    }
    out = mcp_upstream.mcp_upstream_list()
    assert out["count"] == 2
    names = [t["name"] for t in out["servers"]["srv"]]
    assert names == ["read_file", "write_file"]
    assert out["servers"]["srv"][0]["inputSchema"]["type"] == "object"


def test_call_relays_and_serializes():
    session = _FakeSession(_Result([_Text("hello")]))
    mcp_upstream._registry["srv"] = {"session": session, "tools": []}
    out = asyncio.run(mcp_upstream.mcp_upstream_call("srv", "echo", {"a": 1}))
    assert out["isError"] is False
    assert out["content"] == [{"type": "text", "text": "hello"}]
    assert session.calls == [("echo", {"a": 1})]


def test_call_unknown_server_raises():
    with pytest.raises(ValueError):
        asyncio.run(mcp_upstream.mcp_upstream_call("missing", "t", {}))


def test_call_none_arguments_becomes_empty_dict():
    session = _FakeSession(_Result([]))
    mcp_upstream._registry["srv"] = {"session": session, "tools": []}
    asyncio.run(mcp_upstream.mcp_upstream_call("srv", "noargs"))
    assert session.calls == [("noargs", {})]
