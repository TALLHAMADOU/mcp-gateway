from fastapi import APIRouter, HTTPException, Request, Response
import os, httpx

router = APIRouter()
NOTION_TOKEN = os.environ.get('NOTION_TOKEN')
NOTION_API = 'https://api.notion.com/v1'

@router.get('/health')
async def health():
    return {'status': 'ok', 'handler': 'notion', 'configured': bool(NOTION_TOKEN)}

@router.get('/databases/{db_id}/query')
async def query_database(db_id: str, raw: bool = False):
    if not NOTION_TOKEN:
        raise HTTPException(status_code=400, detail='NOTION_TOKEN not configured')
    url = f"{NOTION_API}/databases/{db_id}/query"
    headers = {'Authorization': f'Bearer {NOTION_TOKEN}', 'Notion-Version': '2022-06-28', 'Content-Type': 'application/json'}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, headers=headers)
        return Response(content=r.content, status_code=r.status_code, media_type=r.headers.get('content-type'))

@router.get('/pages/{page_id}')
async def get_page(page_id: str):
    if not NOTION_TOKEN:
        raise HTTPException(status_code=400, detail='NOTION_TOKEN not configured')
    url = f"{NOTION_API}/pages/{page_id}"
    headers = {'Authorization': f'Bearer {NOTION_TOKEN}', 'Notion-Version': '2022-06-28'}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers=headers)
        return Response(content=r.content, status_code=r.status_code, media_type=r.headers.get('content-type'))
