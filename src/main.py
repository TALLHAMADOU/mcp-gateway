from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import JSONResponse, Response
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
import os, yaml, httpx, tempfile, logging, hmac
from .auth import require_api_key, API_KEY
from .mcp_server import mcp, build_mcp_asgi, register_plugin_tools
from .net_guard import is_upstream_url_allowed
from .middleware import RateLimitMiddleware
from .plugin_registry import load_plugins, list_plugins, get_plugin, unload_plugin
from .dashboard import dashboard_router
from .health import health_router
from .logging_config import setup_json_logging
from .audit import setup_audit_logging, read_audit
from .auto_discovery import get_all_tools, generate_tools_json, generate_mcp_registration_script

# Setup JSON logging if LOG_JSON env var is set
setup_json_logging()

# basic logging & audit logger (persisted to an append-only JSONL file)
logging.basicConfig(level=logging.INFO)
audit_logger = setup_audit_logging()

# metrics
try:
    from .metrics import metrics_response, request_counter, auth_failures, rate_limit_hits, proxy_errors, request_latency
except Exception:
    metrics_response = None
    request_counter = None
    auth_failures = None
    rate_limit_hits = None
    proxy_errors = None
    request_latency = None

# SSRF / upstream URL validation lives in net_guard (shared with mcp_server).
_is_upstream_url_allowed = is_upstream_url_allowed

ROOT = os.getcwd()
CONFIG_PATH = os.path.join(ROOT, 'servers.yaml')


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load plugins at startup, then expose them as MCP tools so assistants
    # connected to /mcp can actually call them (not just list them).
    try:
        load_plugins()
        n = register_plugin_tools()
        logging.info(f"Plugins loaded and {n} registered as MCP tools")
    except Exception as e:
        logging.error(f"Failed to load/register plugins: {e}")

    # Run the MCP streamable-HTTP session manager for the mounted /mcp app.
    async with mcp.session_manager.run():
        yield


# Disable the public auto-docs; they are re-exposed below behind the gateway
# API key so the full API surface is not advertised to anonymous callers.
app = FastAPI(title='MCP Gateway', lifespan=lifespan,
              docs_url=None, redoc_url=None, openapi_url=None)
# attach rate limiting middleware (in-memory token buckets)
app.add_middleware(RateLimitMiddleware)

# Native MCP endpoint (Option B): AI assistants connect here over streamable
# HTTP, authenticated with the same gateway API key.
app.mount('/mcp', build_mcp_asgi(API_KEY))

# include builtin handlers under /v1 (all protected by the gateway API key)
from .handlers.fs import router as fs_router
from .handlers.inkscape import router as inkscape_router
from .handlers.gimp import router as gimp_router
from .handlers.krita import router as krita_router
from .handlers.synfig import router as synfig_router
from .handlers.blender import router as blender_router
from .handlers.figma import router as figma_router
from .handlers.google_stitch import router as google_stitch_router
from .handlers.github import router as github_router
from .handlers.db import router as db_router
from .handlers.docker_handler import router as docker_router
from .handlers.chrome_devtools import router as chrome_router
from .handlers.notion import router as notion_router
from .handlers.postgres import router as postgres_router
from .handlers.office import router as office_router
from .handlers.google_workspace import router as gworkspace_router
from .handlers.ms_graph import router as ms_graph_router

_AUTH = [Depends(require_api_key)]

app.include_router(fs_router, prefix='/v1/fs', dependencies=_AUTH)
app.include_router(inkscape_router, prefix='/v1/inkscape', dependencies=_AUTH)
app.include_router(gimp_router, prefix='/v1/gimp', dependencies=_AUTH)
app.include_router(krita_router, prefix='/v1/krita', dependencies=_AUTH)
app.include_router(synfig_router, prefix='/v1/synfig', dependencies=_AUTH)
app.include_router(blender_router, prefix='/v1/blender', dependencies=_AUTH)
app.include_router(figma_router, prefix='/v1/figma', dependencies=_AUTH)
app.include_router(google_stitch_router, prefix='/v1/google-stitch', dependencies=_AUTH)
app.include_router(github_router, prefix='/v1/github', dependencies=_AUTH)
app.include_router(db_router, prefix='/v1/db', dependencies=_AUTH)
app.include_router(docker_router, prefix='/v1/docker', dependencies=_AUTH)
app.include_router(chrome_router, prefix='/v1/chrome', dependencies=_AUTH)
app.include_router(notion_router, prefix='/v1/notion', dependencies=_AUTH)
app.include_router(postgres_router, prefix='/v1/postgres', dependencies=_AUTH)
app.include_router(office_router, prefix='/v1/office', dependencies=_AUTH)
app.include_router(gworkspace_router, prefix='/v1/google-workspace', dependencies=_AUTH)
app.include_router(ms_graph_router, prefix='/v1/ms-graph', dependencies=_AUTH)

# Dashboard / playground UI — protected by the gateway API key like /v1/*.
# (Clients must send Authorization: Bearer <MCP_GATEWAY_KEY>.)
app.include_router(dashboard_router, prefix='/dashboard', dependencies=_AUTH)

# Health checks (no auth required - needed by load balancers/k8s)
app.include_router(health_router)


# OpenAPI schema + interactive docs, gated by the gateway API key.
# Call them with: Authorization: Bearer <MCP_GATEWAY_KEY>
@app.get('/openapi.json', include_in_schema=False)
async def protected_openapi(api_key: str = Depends(require_api_key)):
    return JSONResponse(app.openapi())


@app.get('/docs', include_in_schema=False)
async def protected_docs(api_key: str = Depends(require_api_key)):
    return get_swagger_ui_html(openapi_url='/openapi.json', title='MCP Gateway API')


@app.get('/redoc', include_in_schema=False)
async def protected_redoc(api_key: str = Depends(require_api_key)):
    return get_redoc_html(openapi_url='/openapi.json', title='MCP Gateway API')


def load_config():
    with open(CONFIG_PATH, 'r') as f:
        return yaml.safe_load(f)


@app.get('/v1/connectors')
async def list_connectors(api_key: str = Depends(require_api_key)):
    cfg = load_config()
    if request_latency:
        with request_latency.time():
            return cfg.get('connectors', [])
    return cfg.get('connectors', [])


# prometheus metrics endpoint
if metrics_response:
    @app.get('/metrics')
    async def metrics():
        return metrics_response()


import typing
from fastapi import Header

ADMIN_KEY = os.environ.get('ADMIN_KEY')

@app.post('/v1/admin/register')
async def register_connector(payload: dict, request: Request, api_key: str = Depends(require_api_key), authorization: typing.Optional[str] = Header(None), x_admin_key: typing.Optional[str] = Header(None, alias='X-Admin-Key')):
    # increment request counter
    if request_counter:
        try:
            request_counter.labels(method='POST', path='/v1/admin/register', status='in_progress').inc()
        except Exception:
            pass
    # Only allow registration if ADMIN_KEY is configured
    if not ADMIN_KEY:
        raise HTTPException(status_code=403, detail='Admin registration disabled: ADMIN_KEY not configured')

    # Accept X-Admin-Key header preferentially, fall back to Authorization for backward compatibility
    admin_token = None
    if x_admin_key:
        admin_token = x_admin_key
    elif authorization:
        admin_token = authorization.split(' ', 1)[1] if authorization.lower().startswith('bearer ') else authorization
    if not admin_token:
        raise HTTPException(status_code=401, detail='Missing admin authorization header')
    # constant-time compare
    if not hmac.compare_digest(admin_token, ADMIN_KEY):
        raise HTTPException(status_code=403, detail='Invalid admin key')

    # validate payload
    if not isinstance(payload, dict) or 'id' not in payload:
        raise HTTPException(status_code=400, detail='payload must be a dict with at least an "id" field')
    cfg = load_config()
    existing = next((c for c in cfg.get('connectors', []) if c.get('id') == payload.get('id')), None)
    if existing:
        raise HTTPException(status_code=409, detail='connector with given id already exists')
    # basic shape validation
    if not payload.get('type') and not payload.get('handler') and not payload.get('url'):
        raise HTTPException(status_code=400, detail='connector must include type and handler or url')
    # enforce https for remote connectors
    if payload.get('url') and not str(payload.get('url')).startswith('https://'):
        raise HTTPException(status_code=400, detail='remote connector url must use https://')
    # SSRF protection: reject private or loopback addresses
    if payload.get('url') and not _is_upstream_url_allowed(payload.get('url')):
        raise HTTPException(status_code=403, detail='remote connector url resolves to a forbidden/ private address')

    cfg.setdefault('connectors', []).append(payload)
    # atomic write to avoid partial writes / races
    tmp_fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(CONFIG_PATH) or '.')
    try:
        with os.fdopen(tmp_fd, 'w') as tmp:
            yaml.safe_dump(cfg, tmp)
        os.replace(tmp_path, CONFIG_PATH)
    finally:
        # best-effort cleanup
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass

    # audit log
    try:
        masked = f"{str(api_key)[:4]}..." if api_key else 'unknown'
        audit_logger.info('admin.register', extra={'actor': masked, 'connector_id': payload.get('id'), 'url': payload.get('url')})
    except Exception:
        pass

    # increment request counter success
    if request_counter:
        try:
            request_counter.labels(method='POST', path='/v1/admin/register', status='200').inc()
        except Exception:
            pass

    return {'ok': True, 'connector': payload}


@app.get('/v1/audit')
async def get_audit(limit: int = 100, api_key: str = Depends(require_api_key), x_admin_key: typing.Optional[str] = Header(None, alias='X-Admin-Key')):
    """Read recent persisted audit entries (requires the admin key)."""
    if not ADMIN_KEY:
        raise HTTPException(status_code=403, detail='Audit access disabled: ADMIN_KEY not configured')
    if not x_admin_key:
        raise HTTPException(status_code=401, detail='Missing X-Admin-Key header')
    if not hmac.compare_digest(x_admin_key, ADMIN_KEY):
        raise HTTPException(status_code=403, detail='Invalid admin key')
    entries = read_audit(limit)
    return {'count': len(entries), 'entries': entries}


@app.api_route('/v1/proxy/{connector_id}/{path:path}', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
async def proxy(connector_id: str, path: str, request: Request, api_key: str = Depends(require_api_key)):
    cfg = load_config()
    connector = next((c for c in cfg.get('connectors', []) if c.get('id') == connector_id), None)
    if not connector:
        raise HTTPException(status_code=404, detail='connector not found')

    if connector.get('type') == 'remote' and connector.get('url'):
        target = connector['url'].rstrip('/') + '/' + path
        # Audit proxy usage
        try:
            masked = f"{str(api_key)[:4]}..." if api_key else 'unknown'
            audit_logger.info('proxy.request', extra={'actor': masked, 'connector_id': connector_id, 'target': target, 'method': request.method})
        except Exception:
            pass
        # SSRF protection: ensure target resolves to allowed IPs
        if not _is_upstream_url_allowed(target):
            raise HTTPException(status_code=403, detail='upstream connector resolves to a forbidden/private address')
        async with httpx.AsyncClient() as client:
            # Strip hop-by-hop and gateway-auth headers so the gateway API key
            # and Host are never leaked to the upstream connector.
            _STRIP = {'host', 'authorization', 'content-length', 'connection'}
            req_headers = {k: v for k, v in request.headers.items() if k.lower() not in _STRIP}
            body = await request.body()
            resp = await client.request(request.method, target, headers=req_headers, content=body)
            # httpx already decoded the body, so drop length/encoding headers that
            # would otherwise describe the original (compressed/chunked) stream.
            _DROP = {'content-encoding', 'content-length', 'transfer-encoding', 'connection'}
            resp_headers = {k: v for k, v in resp.headers.items() if k.lower() not in _DROP}
            return Response(content=resp.content, status_code=resp.status_code, headers=resp_headers)

    return JSONResponse({'error': 'connector type not supported by proxy'}, status_code=400)


# ==================== AUTO-DISCOVERY (MCP/REST) ====================

@app.get('/v1/auto-discovery/tools')
async def list_all_tools(api_key: str = Depends(require_api_key)):
    """List all available tools (REST endpoint)."""
    return generate_tools_json()


@app.get('/v1/auto-discovery/registration')
async def get_registration_script(api_key: str = Depends(require_api_key)):
    """Get MCP registration script for Claude Desktop, Cursor, etc."""
    gateway_url = os.environ.get('GATEWAY_URL') or os.environ.get('MCP_GATEWAY_URL', 'http://localhost:8080')
    script = generate_mcp_registration_script(gateway_url=gateway_url, api_key=api_key)
    return JSONResponse({"script": script})


@app.post('/v1/auto-discovery/register')
async def save_registration(payload: dict, api_key: str = Depends(require_api_key)):
    """Save registration configuration (generates config file)."""
    client_type = payload.get("client_type", "claude-desktop")  # claude-desktop, cursor, copilot-cli
    gateway_url = payload.get("gateway_url", "http://localhost:8080")
    
    # Generate appropriate config based on client type
    if client_type == "claude-desktop":
        config = {
            "mcpServers": {
                "gateway": {
                    "url": f"{gateway_url}/mcp",
                    "env": {
                        "MCP_GATEWAY_KEY": api_key
                    }
                }
            }
        }
    elif client_type == "cursor":
        config = {
            "mcpServers": {
                "gateway": {
                    "url": f"{gateway_url}/mcp",
                    "env": {
                        "MCP_GATEWAY_KEY": api_key
                    }
                }
            }
        }
    else:
        config = {"error": f"Unknown client type: {client_type}"}
    
    return {
        "client_type": client_type,
        "config": config,
        "instructions": f"Copy this config to your {client_type} configuration file."
    }


# ==================== PLUGIN SYSTEM ====================

@app.get('/v1/plugins')
async def list_all_plugins(api_key: str = Depends(require_api_key)):
    """List all loaded plugins with metadata."""
    plugins = list_plugins()
    return {
        "count": len(plugins),
        "plugins": plugins
    }


@app.post('/v1/plugins/{plugin_id}/execute')
async def execute_plugin(plugin_id: str, payload: dict, request: Request, api_key: str = Depends(require_api_key)):
    """Execute a plugin tool with the given arguments."""
    tool = get_plugin(plugin_id)
    if not tool:
        raise HTTPException(status_code=404, detail=f"Plugin not found: {plugin_id}")
    
    try:
        # Audit plugin execution
        try:
            masked = f"{str(api_key)[:4]}..." if api_key else 'unknown'
            audit_logger.info('plugin.execute', extra={'actor': masked, 'plugin_id': plugin_id})
        except Exception:
            pass
        
        # Execute the plugin function
        result = await tool.call(**payload)
        return {
            "plugin_id": plugin_id,
            "success": True,
            "result": result
        }
    except TypeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid arguments: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Plugin execution failed: {str(e)}")


@app.delete('/v1/plugins/{plugin_id}')
async def delete_plugin(plugin_id: str, api_key: str = Depends(require_api_key), x_admin_key: typing.Optional[str] = Header(None, alias='X-Admin-Key')):
    """Unload a plugin (requires admin key)."""
    # Only allow deletion if ADMIN_KEY is configured
    if not ADMIN_KEY:
        raise HTTPException(status_code=403, detail='Admin key not configured')
    
    admin_token = x_admin_key
    if not admin_token:
        raise HTTPException(status_code=401, detail='Missing X-Admin-Key header')
    
    if not hmac.compare_digest(admin_token, ADMIN_KEY):
        raise HTTPException(status_code=403, detail='Invalid admin key')
    
    if unload_plugin(plugin_id):
        return {"ok": True, "message": f"Plugin {plugin_id} unloaded"}
    else:
        raise HTTPException(status_code=404, detail=f"Plugin not found: {plugin_id}")
