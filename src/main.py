from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import JSONResponse, Response
import os, yaml, httpx, tempfile
from .auth import require_api_key, API_KEY
from .mcp_server import mcp, build_mcp_asgi

ROOT = os.getcwd()
CONFIG_PATH = os.path.join(ROOT, 'servers.yaml')


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Run the MCP streamable-HTTP session manager for the mounted /mcp app.
    async with mcp.session_manager.run():
        yield


app = FastAPI(title='MCP Gateway', lifespan=lifespan)

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


def load_config():
    with open(CONFIG_PATH, 'r') as f:
        return yaml.safe_load(f)


@app.get('/v1/connectors')
async def list_connectors(api_key: str = Depends(require_api_key)):
    cfg = load_config()
    return cfg.get('connectors', [])


import typing
from fastapi import Header

ADMIN_KEY = os.environ.get('ADMIN_KEY')

@app.post('/v1/admin/register')
async def register_connector(payload: dict, request: Request, api_key: str = Depends(require_api_key), authorization: typing.Optional[str] = Header(None)):
    # Only allow registration if ADMIN_KEY is configured
    if not ADMIN_KEY:
        raise HTTPException(status_code=403, detail='Admin registration disabled: ADMIN_KEY not configured')

    # Require admin authorization header and validate it
    if not authorization:
        raise HTTPException(status_code=401, detail='Missing Authorization header for admin')
    token = authorization.split(' ', 1)[1] if authorization.lower().startswith('bearer ') else authorization
    if token != ADMIN_KEY:
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

    return {'ok': True, 'connector': payload}


@app.api_route('/v1/proxy/{connector_id}/{path:path}', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
async def proxy(connector_id: str, path: str, request: Request, api_key: str = Depends(require_api_key)):
    cfg = load_config()
    connector = next((c for c in cfg.get('connectors', []) if c.get('id') == connector_id), None)
    if not connector:
        raise HTTPException(status_code=404, detail='connector not found')

    if connector.get('type') == 'remote' and connector.get('url'):
        target = connector['url'].rstrip('/') + '/' + path
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
