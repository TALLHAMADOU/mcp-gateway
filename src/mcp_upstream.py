"""Bridge to upstream MCP servers (the "cas C" of the README).

Lets operators plug *any* third-party MCP server into the gateway through
configuration alone — no code — and re-expose its tools under ``/mcp``. This is
the standard ``mcpServers`` idea (Claude Desktop, Cursor, …) but centralised in
the gateway so a single connection serves every assistant behind it.

Two transports:
  * ``http``  — a remote streamable-HTTP MCP server (SSRF-guarded).
  * ``stdio`` — a local MCP server process. This spawns an arbitrary command,
                so it is **opt-in** via ``MCP_UPSTREAM_ENABLE_STDIO=1`` (it
                otherwise contradicts the hardened non-root/read-only runtime).

Discovery and invocation are exposed as two generic MCP tools
(``mcp_upstream_list`` / ``mcp_upstream_call``): the former returns each
upstream tool's real JSON input schema, the latter relays a call. This keeps the
bridge robust across FastMCP versions (no reliance on per-tool schema injection).

Config file (default ``mcp_servers.yaml``, override with ``MCP_SERVERS_CONFIG``):

    mcp_servers:
      filesystem:
        transport: stdio
        command: npx
        args: ["-y", "@modelcontextprotocol/server-filesystem", "/data"]
        env: { SOME_FLAG: "1" }
      company:
        transport: http
        url: https://mcp.example.com/mcp
        headers: { Authorization: "Bearer ${COMPANY_TOKEN}" }
        # disabled: true   # skip without deleting the entry

``${VAR}`` placeholders anywhere in the config are filled from the environment,
so secrets stay out of the file.
"""
import logging
import os
import re
from contextlib import AsyncExitStack

import yaml

from .net_guard import is_upstream_url_allowed
from .mcp_server import mcp

log = logging.getLogger(__name__)

# name -> {"session": ClientSession, "tools": [Tool, ...]}
_registry: dict = {}
_stack: "AsyncExitStack | None" = None

_VAR = re.compile(r"\$\{(\w+)\}")


def _expand(obj):
    """Recursively replace ``${VAR}`` with the environment value (or '')."""
    if isinstance(obj, str):
        return _VAR.sub(lambda m: os.environ.get(m.group(1), ""), obj)
    if isinstance(obj, dict):
        return {k: _expand(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_expand(v) for v in obj]
    return obj


def _config_path() -> str:
    return os.environ.get("MCP_SERVERS_CONFIG", "mcp_servers.yaml")


def _load_config() -> dict:
    """Return ``{server_name: config}`` from the config file ({} if absent)."""
    path = _config_path()
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        data = yaml.safe_load(f) or {}
    servers = data.get("mcp_servers") or {}
    if not isinstance(servers, dict):
        raise RuntimeError("'mcp_servers' must be a mapping of name -> config")
    return {name: _expand(cfg or {}) for name, cfg in servers.items()}


def _stdio_enabled() -> bool:
    return os.environ.get("MCP_UPSTREAM_ENABLE_STDIO", "").lower() in (
        "1", "true", "yes", "on")


async def _connect_one(name: str, cfg: dict, stack: AsyncExitStack):
    """Open a session to one upstream server and return (session, tools)."""
    transport = str(cfg.get("transport", "")).lower()

    if transport == "http":
        url = cfg.get("url")
        if not url:
            raise ValueError("http transport requires 'url'")
        if not is_upstream_url_allowed(url):
            raise ValueError(f"url blocked by SSRF guard: {url}")
        from mcp.client.streamable_http import streamablehttp_client
        streams = await stack.enter_async_context(
            streamablehttp_client(url, headers=cfg.get("headers") or None))
        read, write, *_ = streams

    elif transport == "stdio":
        if not _stdio_enabled():
            raise RuntimeError(
                "stdio transport disabled; set MCP_UPSTREAM_ENABLE_STDIO=1 to allow "
                "spawning local MCP server processes")
        command = cfg.get("command")
        if not command:
            raise ValueError("stdio transport requires 'command'")
        from mcp.client.stdio import stdio_client, StdioServerParameters
        params = StdioServerParameters(
            command=command, args=cfg.get("args") or [], env=cfg.get("env") or None)
        read, write, *_ = await stack.enter_async_context(stdio_client(params))

    else:
        raise ValueError(f"unknown transport {transport!r} (use 'http' or 'stdio')")

    from mcp.client.session import ClientSession
    session = await stack.enter_async_context(ClientSession(read, write))
    await session.initialize()
    tools = (await session.list_tools()).tools
    return session, tools


async def startup() -> int:
    """Connect every configured upstream server. Returns the tool count.

    Failures are isolated: a server that cannot be reached is logged and
    skipped — it never prevents the gateway from starting.
    """
    global _stack
    cfg = _load_config()
    if not cfg:
        return 0

    _stack = AsyncExitStack()
    await _stack.__aenter__()
    total = 0
    for name, server_cfg in cfg.items():
        if server_cfg.get("disabled"):
            log.info("mcp-upstream: %r disabled, skipping", name)
            continue
        try:
            session, tools = await _connect_one(name, server_cfg, _stack)
        except Exception:
            log.exception("mcp-upstream: failed to connect %r (skipped)", name)
            continue
        _registry[name] = {"session": session, "tools": tools}
        total += len(tools)
        log.info("mcp-upstream: connected %r (%d tools)", name, len(tools))
    return total


async def shutdown() -> None:
    """Close all upstream sessions/transports."""
    global _stack
    _registry.clear()
    if _stack is not None:
        try:
            await _stack.aclose()
        except Exception:
            log.exception("mcp-upstream: error during shutdown")
        _stack = None


def _serialize_result(result) -> dict:
    """Turn a CallToolResult into a JSON-serialisable dict."""
    out = {"isError": bool(getattr(result, "isError", False)), "content": []}
    for block in getattr(result, "content", None) or []:
        if getattr(block, "type", None) == "text":
            out["content"].append({"type": "text", "text": getattr(block, "text", "")})
        else:
            try:
                out["content"].append(block.model_dump(mode="json"))
            except Exception:
                out["content"].append({"type": getattr(block, "type", "unknown"),
                                       "repr": str(block)})
    structured = getattr(result, "structuredContent", None)
    if structured is not None:
        out["structuredContent"] = structured
    return out


# --- generic bridge tools (registered on the gateway's MCP server) ----------

@mcp.tool()
def mcp_upstream_list() -> dict:
    """List tools exposed by the configured upstream MCP servers.

    Returns each server's tools with their name, description and JSON
    inputSchema — use it to learn what to pass to ``mcp_upstream_call``.
    """
    servers = {}
    for name, entry in _registry.items():
        servers[name] = [
            {"name": t.name,
             "description": getattr(t, "description", None),
             "inputSchema": getattr(t, "inputSchema", None)}
            for t in entry["tools"]
        ]
    return {"servers": servers, "count": sum(len(v) for v in servers.values())}


@mcp.tool()
async def mcp_upstream_call(server: str, tool: str, arguments: dict | None = None) -> dict:
    """Call a tool on a configured upstream MCP server.

    `server` and `tool` come from ``mcp_upstream_list``; `arguments` matches the
    tool's inputSchema.
    """
    entry = _registry.get(server)
    if not entry:
        raise ValueError(f"upstream MCP server not connected: {server}")
    result = await entry["session"].call_tool(tool, arguments or {})
    return _serialize_result(result)
