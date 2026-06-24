"""Option B — native MCP server (streamable HTTP).

Exposes the gateway's connectors as MCP *tools*, calling the existing handler
logic **in-process** (no self-HTTP hop). Mounted at ``/mcp`` by ``src/main.py``
and guarded by the same gateway API key.

Assistants (Claude Code, Codex, Gemini CLI, Copilot CLI) connect to
``https://<host>/mcp`` with an ``Authorization: Bearer <MCP_GATEWAY_KEY>`` header.
"""
import os
import httpx
import yaml
import hmac
from starlette.concurrency import run_in_threadpool
from mcp.server.fastmcp import FastMCP

from .handlers import fs as fs_handler
from .handlers import postgres as pg_handler
from .handlers import db as db_handler
from .handlers import docker_handler
from .handlers.github import gh_get
from .handlers.notion import NOTION_TOKEN, NOTION_API
from .handlers.figma import FIGMA_TOKEN, FIGMA_API
from .handlers.chrome_devtools import CDP_HOST
from .handlers import office as office_handler
from .handlers import google_workspace as gws
from .handlers import ms_graph as msg
from .sql_guard import validate_select

mcp = FastMCP("MCP Gateway")
# Stateless keeps mounting simple; serve the endpoint at the mount root so the
# full path is exactly "/mcp" (not "/mcp/mcp").
mcp.settings.stateless_http = True
mcp.settings.streamable_http_path = "/"


# --- connectors registry ----------------------------------------------------
@mcp.tool()
def list_connectors() -> list:
    """List the connectors declared in servers.yaml."""
    path = os.path.join(os.getcwd(), "servers.yaml")
    with open(path) as f:
        return (yaml.safe_load(f) or {}).get("connectors", [])


# --- filesystem (sandboxed via fs_handler._resolve) -------------------------
@mcp.tool()
def fs_list(path: str = ".") -> dict:
    """List a directory inside the gateway filesystem sandbox."""
    target = fs_handler._resolve(path)
    if not os.path.isdir(target):
        raise ValueError("not a directory")
    try:
        from .metrics import request_counter, request_latency
        if request_latency:
            with request_latency.time():
                return {"path": path, "entries": [
                    {"name": n, "is_dir": os.path.isdir(os.path.join(target, n))}
                    for n in os.listdir(target)
                ]}
    except Exception:
        pass
    return {"path": path, "entries": [
        {"name": n, "is_dir": os.path.isdir(os.path.join(target, n))}
        for n in os.listdir(target)
    ]}


@mcp.tool()
def fs_read(path: str) -> str:
    """Read a UTF-8 text file inside the filesystem sandbox."""
    target = fs_handler._resolve(path)
    if not os.path.isfile(target):
        raise ValueError("file not found")
    with open(target, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


# --- SQL (read-only) --------------------------------------------------------
@mcp.tool()
async def pg_query(sql: str, params: list | None = None) -> dict:
    """Run a read-only SELECT against the configured Postgres (POSTGRES_DSN)."""
    dsn = pg_handler.POSTGRES_DSN
    if not dsn:
        raise ValueError("Postgres DSN not configured (POSTGRES_DSN / DATABASE_URL)")
    return await run_in_threadpool(pg_handler._run_query, dsn, sql, params)


@mcp.tool()
async def sqlite_query(db_path: str, sql: str, params: list | None = None) -> dict:
    """Run a read-only SELECT against a local SQLite file."""
    sql = validate_select(sql)
    return await run_in_threadpool(db_handler._run_sqlite_query, db_path, sql, params)


# --- GitHub -----------------------------------------------------------------
@mcp.tool()
async def github_repo(owner: str, repo: str) -> dict:
    """Fetch GitHub repository metadata."""
    return (await gh_get(f"repos/{owner}/{repo}")).json()


@mcp.tool()
async def github_issues(owner: str, repo: str, state: str = "open") -> list:
    """List GitHub issues for a repository (state: open/closed/all)."""
    return (await gh_get(f"repos/{owner}/{repo}/issues", params={"state": state})).json()


@mcp.tool()
async def github_pulls(owner: str, repo: str, state: str = "open") -> list:
    """List GitHub pull requests for a repository (state: open/closed/all)."""
    return (await gh_get(f"repos/{owner}/{repo}/pulls", params={"state": state})).json()


# --- Notion -----------------------------------------------------------------
@mcp.tool()
async def notion_page(page_id: str) -> dict:
    """Fetch a Notion page by id (requires NOTION_TOKEN)."""
    if not NOTION_TOKEN:
        raise ValueError("NOTION_TOKEN not configured")
    headers = {"Authorization": f"Bearer {NOTION_TOKEN}", "Notion-Version": "2022-06-28"}
    async with httpx.AsyncClient(timeout=30) as c:
        return (await c.get(f"{NOTION_API}/pages/{page_id}", headers=headers)).json()


@mcp.tool()
async def notion_db_query(database_id: str) -> dict:
    """Query a Notion database by id (requires NOTION_TOKEN)."""
    if not NOTION_TOKEN:
        raise ValueError("NOTION_TOKEN not configured")
    headers = {"Authorization": f"Bearer {NOTION_TOKEN}", "Notion-Version": "2022-06-28",
               "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as c:
        return (await c.post(f"{NOTION_API}/databases/{database_id}/query",
                             headers=headers)).json()


# --- Figma ------------------------------------------------------------------
@mcp.tool()
async def figma_file(file_key: str, node_id: str | None = None) -> dict:
    """Fetch a Figma file (optionally a specific node) — requires FIGMA_TOKEN."""
    if not FIGMA_TOKEN:
        raise ValueError("FIGMA_TOKEN not configured")
    params = {"ids": node_id} if node_id else None
    async with httpx.AsyncClient(timeout=30) as c:
        return (await c.get(f"{FIGMA_API}/files/{file_key}",
                            headers={"X-Figma-Token": FIGMA_TOKEN}, params=params)).json()


# --- Docker (inspection) ----------------------------------------------------
@mcp.tool()
async def docker_ps() -> list:
    """List Docker containers (all states)."""
    return await run_in_threadpool(docker_handler._ps)


@mcp.tool()
async def docker_images() -> list:
    """List Docker images."""
    return await run_in_threadpool(docker_handler._images)


@mcp.tool()
async def docker_inspect(id_or_name: str) -> dict:
    """Inspect a Docker container by id or name."""
    return await run_in_threadpool(docker_handler._inspect, id_or_name)


# --- Chrome DevTools --------------------------------------------------------
@mcp.tool()
async def chrome_targets() -> list:
    """List Chrome DevTools targets (CHROME_DEBUG_HOST)."""
    async with httpx.AsyncClient(timeout=10) as c:
        return (await c.get(f"{CDP_HOST}/json")).json()


# --- Office (local generation + LibreOffice conversion) ---------------------
@mcp.tool()
async def office_create_docx(spec: dict) -> dict:
    """Create a .docx. spec: {filename, elements:[{type:heading|paragraph|bullet, text, level}]}."""
    return {"path": await run_in_threadpool(office_handler.make_docx, spec)}


@mcp.tool()
async def office_create_xlsx(spec: dict) -> dict:
    """Create a .xlsx. spec: {filename, sheets:[{name, rows:[[...],...]}]}."""
    return {"path": await run_in_threadpool(office_handler.make_xlsx, spec)}


@mcp.tool()
async def office_create_pptx(spec: dict) -> dict:
    """Create a .pptx. spec: {filename, slides:[{title, bullets:[...] | body}]}."""
    return {"path": await run_in_threadpool(office_handler.make_pptx, spec)}


@mcp.tool()
async def office_convert(source_path: str, to: str) -> dict:
    """Convert/export a document via LibreOffice headless (e.g. to='pdf')."""
    return {"path": await run_in_threadpool(office_handler.convert_file, source_path, to)}


# --- Google Workspace -------------------------------------------------------
@mcp.tool()
async def gdrive_files(q: str | None = None, page_size: int = 50) -> dict:
    """List Google Drive files (optional Drive query `q`)."""
    return await gws.drive_files(q=q, page_size=page_size)


@mcp.tool()
async def gdoc_get(document_id: str) -> dict:
    """Fetch a Google Doc by id."""
    return await gws.get_doc(document_id)


@mcp.tool()
async def gdoc_create(title: str) -> dict:
    """Create a new empty Google Doc."""
    return await gws.create_doc({"title": title})


@mcp.tool()
async def gsheet_values(spreadsheet_id: str, range_a1: str) -> dict:
    """Read values from a Google Sheet range (A1 notation)."""
    return await gws.get_sheet_values(spreadsheet_id, range_a1)


@mcp.tool()
async def gslides_get(presentation_id: str) -> dict:
    """Fetch a Google Slides presentation by id."""
    return await gws.get_slides(presentation_id)


# --- Microsoft 365 (Graph) --------------------------------------------------
@mcp.tool()
async def onedrive_root() -> dict:
    """List the root of the user's OneDrive."""
    return await msg.onedrive_root()


@mcp.tool()
async def onedrive_search(q: str) -> dict:
    """Search files in OneDrive."""
    return await msg.search_files(q)


@mcp.tool()
async def msexcel_worksheets(item_id: str) -> dict:
    """List worksheets of an Excel workbook stored in OneDrive (drive item id)."""
    return await msg.excel_worksheets(item_id)


@mcp.tool()
async def msexcel_range(item_id: str, name: str) -> dict:
    """Read the used range of a worksheet in an Excel workbook on OneDrive."""
    return await msg.excel_used_range(item_id, name)


# --- ASGI auth wrapper for the mounted MCP app ------------------------------
class BearerAuthASGI:
    """Guards the mounted MCP ASGI app with the gateway API key."""

    def __init__(self, app, api_key: str):
        self.app = app
        self.api_key = api_key

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = dict(scope.get("headers") or [])
        raw = headers.get(b"authorization", b"").decode()
        token = raw[7:] if raw[:7].lower() == "bearer " else raw
        # constant-time comparison to prevent timing attacks
        if not hmac.compare_digest(token, self.api_key):
            await send({"type": "http.response.start", "status": 401,
                        "headers": [(b"content-type", b"application/json")]})
            await send({"type": "http.response.body",
                        "body": b'{"detail":"Invalid or missing API key"}'})
            return
        await self.app(scope, receive, send)


def build_mcp_asgi(api_key: str):
    """Return the MCP streamable-HTTP app wrapped with bearer auth."""
    return BearerAuthASGI(mcp.streamable_http_app(), api_key)
