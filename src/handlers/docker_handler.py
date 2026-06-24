from fastapi import APIRouter, HTTPException
from starlette.concurrency import run_in_threadpool
import docker
import copy

router = APIRouter()

@router.get('/health')
async def health():
    return {'status': 'ok', 'handler': 'docker'}

def _docker_client():
    return docker.from_env()

def _sanitize_container(attrs: dict) -> dict:
    # Return a copy with sensitive fields removed (env, host config)
    a = copy.deepcopy(attrs)
    # Remove environment variables
    try:
        if 'Config' in a and isinstance(a['Config'], dict):
            a['Config'].pop('Env', None)
            # keep other config fields
    except Exception:
        pass
    # Remove HostConfig which may contain mounts/ binds with secrets
    a.pop('HostConfig', None)
    return a

def _ps():
    client = _docker_client()
    return [_sanitize_container(c.attrs) for c in client.containers.list(all=True)]

def _images():
    client = _docker_client()
    # images.attrs may contain container config; scrub if present
    res = []
    for i in client.images.list():
        try:
            a = copy.deepcopy(i.attrs)
            if 'ContainerConfig' in a and isinstance(a['ContainerConfig'], dict):
                a['ContainerConfig'].pop('Env', None)
            res.append(a)
        except Exception:
            res.append({})
    return res

def _inspect(id_or_name: str):
    client = _docker_client()
    c = client.containers.get(id_or_name)
    return _sanitize_container(c.attrs)

@router.get('/ps')
async def ps():
    try:
        res = await run_in_threadpool(_ps)
        return {'containers': res}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get('/images')
async def images():
    try:
        res = await run_in_threadpool(_images)
        return {'images': res}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get('/inspect/{id_or_name}')
async def inspect(id_or_name: str):
    try:
        res = await run_in_threadpool(_inspect, id_or_name)
        return {'inspect': res}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
