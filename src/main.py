from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import JSONResponse, Response
import os, yaml, httpx
from .auth import require_api_key
from .handlers.fs import router as fs_router

ROOT = os.getcwd()
CONFIG_PATH = os.path.join(ROOT, 'servers.yaml')

app = FastAPI(title='MCP Gateway')

# include builtin handlers under /v1
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

app.include_router(fs_router, prefix='/v1/fs')
app.include_router(inkscape_router, prefix='/v1/inkscape')
app.include_router(gimp_router, prefix='/v1/gimp')
app.include_router(krita_router, prefix='/v1/krita')
app.include_router(synfig_router, prefix='/v1/synfig')
app.include_router(blender_router, prefix='/v1/blender')
app.include_router(figma_router, prefix='/v1/figma')
app.include_router(google_stitch_router, prefix='/v1/google-stitch')
app.include_router(github_router, prefix='/v1/github')
app.include_router(db_router, prefix='/v1/db')
app.include_router(docker_router, prefix='/v1/docker')
app.include_router(chrome_router, prefix='/v1/chrome')
app.include_router(notion_router, prefix='/v1/notion')
app.include_router(postgres_router, prefix='/v1/postgres')


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
    # Require ADMIN_KEY if set
    if ADMIN_KEY:
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
    cfg.setdefault('connectors', []).append(payload)
    with open(CONFIG_PATH, 'w') as f:
        yaml.safe_dump(cfg, f)
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
            req_headers = {k: v for k, v in request.headers.items() if k.lower() != 'host'}
            body = await request.body()
            resp = await client.request(request.method, target, headers=req_headers, content=body)
            return Response(content=resp.content, status_code=resp.status_code, headers=dict(resp.headers))

    return JSONResponse({'error': 'connector type not supported by proxy'}, status_code=400)
