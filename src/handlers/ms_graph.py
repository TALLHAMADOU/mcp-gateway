"""Microsoft 365 proxy via Microsoft Graph — OneDrive / Word / Excel / PPT.

Auth: a Graph access token (`MS_GRAPH_TOKEN`) obtained from an Azure AD app
registration (client-credentials or delegated flow). This is the portable way
to reach Office 365 from a Linux host — the desktop Office pack on Windows is
NOT driven from here.
"""
from fastapi import APIRouter, HTTPException, Response
import os
import httpx

router = APIRouter()

MS_GRAPH_TOKEN = os.environ.get('MS_GRAPH_TOKEN')
GRAPH = 'https://graph.microsoft.com/v1.0'


def _headers():
    if not MS_GRAPH_TOKEN:
        raise HTTPException(status_code=400, detail='MS_GRAPH_TOKEN not configured')
    return {'Authorization': f'Bearer {MS_GRAPH_TOKEN}'}


async def graph_get(path: str, *, params=None, raw=False):
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(f'{GRAPH}/{path.lstrip("/")}', headers=_headers(), params=params)
        if r.status_code >= 400:
            raise HTTPException(status_code=r.status_code, detail=r.text)
        return r if raw else r.json()


@router.get('/health')
async def health():
    return {'status': 'ok', 'handler': 'ms_graph', 'configured': bool(MS_GRAPH_TOKEN)}


@router.get('/onedrive/root')
async def onedrive_root():
    return await graph_get('me/drive/root/children')


@router.get('/onedrive/item/{item_id}')
async def onedrive_item(item_id: str):
    return await graph_get(f'me/drive/items/{item_id}')


@router.get('/onedrive/item/{item_id}/content')
async def onedrive_download(item_id: str):
    r = await graph_get(f'me/drive/items/{item_id}/content', raw=True)
    return Response(content=r.content, status_code=r.status_code,
                    media_type=r.headers.get('content-type', 'application/octet-stream'))


@router.get('/excel/{item_id}/worksheets')
async def excel_worksheets(item_id: str):
    return await graph_get(f'me/drive/items/{item_id}/workbook/worksheets')


@router.get('/excel/{item_id}/worksheet/{name}/range')
async def excel_used_range(item_id: str, name: str):
    return await graph_get(f'me/drive/items/{item_id}/workbook/worksheets/{name}/usedRange')


@router.get('/search')
async def search_files(q: str):
    return await graph_get(f"me/drive/root/search(q='{q}')")
