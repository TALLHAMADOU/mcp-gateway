from fastapi import APIRouter, HTTPException, Request, Response
import os, httpx

router = APIRouter()

FIGMA_TOKEN = os.environ.get('FIGMA_TOKEN')
FIGMA_API = 'https://api.figma.com/v1'

@router.get('/health')
async def health():
    return {'status': 'ok', 'handler': 'figma', 'configured': bool(FIGMA_TOKEN)}

@router.get('/file/{file_key}')
async def get_file(file_key: str, node_id: str | None = None):
    if not FIGMA_TOKEN:
        raise HTTPException(status_code=400, detail='FIGMA_TOKEN not configured')
    url = f"{FIGMA_API}/files/{file_key}"
    params = {'ids': node_id} if node_id else None
    headers = {'X-Figma-Token': FIGMA_TOKEN}
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, headers=headers, params=params)
        return Response(content=resp.content, status_code=resp.status_code, media_type=resp.headers.get('content-type'))

@router.post('/file/{file_key}/images')
async def get_images(file_key: str, payload: dict):
    if not FIGMA_TOKEN:
        raise HTTPException(status_code=400, detail='FIGMA_TOKEN not configured')
    url = f"{FIGMA_API}/images/{file_key}"
    headers = {'X-Figma-Token': FIGMA_TOKEN}
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, headers=headers, params=payload)
        return Response(content=resp.content, status_code=resp.status_code, media_type=resp.headers.get('content-type'))
