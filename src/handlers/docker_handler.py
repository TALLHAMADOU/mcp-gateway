from fastapi import APIRouter, HTTPException
from starlette.concurrency import run_in_threadpool
import docker

router = APIRouter()

@router.get('/health')
async def health():
    return {'status': 'ok', 'handler': 'docker'}

def _docker_client():
    return docker.from_env()

def _ps():
    client = _docker_client()
    return [c.attrs for c in client.containers.list(all=True)]

def _images():
    client = _docker_client()
    return [i.attrs for i in client.images.list()]

def _inspect(id_or_name: str):
    client = _docker_client()
    c = client.containers.get(id_or_name)
    return c.attrs

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
