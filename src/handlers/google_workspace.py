"""Google Workspace proxy — Drive / Docs / Sheets / Slides.

Auth: an OAuth2 access token with the right scopes, supplied via
`GOOGLE_ACCESS_TOKEN` (same env-token pattern as the github/notion handlers).
Mint it from a service account or the OAuth playground; the gateway only
forwards it as a bearer token.
"""
from fastapi import APIRouter, HTTPException
import os
import httpx

router = APIRouter()

GOOGLE_ACCESS_TOKEN = os.environ.get('GOOGLE_ACCESS_TOKEN')
DRIVE = 'https://www.googleapis.com/drive/v3'
DOCS = 'https://docs.googleapis.com/v1'
SHEETS = 'https://sheets.googleapis.com/v4'
SLIDES = 'https://slides.googleapis.com/v1'


def _headers():
    if not GOOGLE_ACCESS_TOKEN:
        raise HTTPException(status_code=400, detail='GOOGLE_ACCESS_TOKEN not configured')
    return {'Authorization': f'Bearer {GOOGLE_ACCESS_TOKEN}', 'Content-Type': 'application/json'}


async def g_request(method: str, url: str, *, params=None, json=None):
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.request(method, url, headers=_headers(), params=params, json=json)
        if r.status_code >= 400:
            raise HTTPException(status_code=r.status_code, detail=r.text)
        return r.json()


@router.get('/health')
async def health():
    return {'status': 'ok', 'handler': 'google_workspace', 'configured': bool(GOOGLE_ACCESS_TOKEN)}


@router.get('/drive/files')
async def drive_files(q: str | None = None, page_size: int = 50):
    params = {'pageSize': page_size, 'fields': 'files(id,name,mimeType,modifiedTime)'}
    if q:
        params['q'] = q
    return await g_request('GET', f'{DRIVE}/files', params=params)


@router.get('/docs/{document_id}')
async def get_doc(document_id: str):
    return await g_request('GET', f'{DOCS}/documents/{document_id}')


@router.post('/docs')
async def create_doc(payload: dict):
    return await g_request('POST', f'{DOCS}/documents', json={'title': payload.get('title', 'Untitled')})


@router.get('/sheets/{spreadsheet_id}')
async def get_sheet(spreadsheet_id: str):
    return await g_request('GET', f'{SHEETS}/spreadsheets/{spreadsheet_id}')


@router.get('/sheets/{spreadsheet_id}/values/{range_a1}')
async def get_sheet_values(spreadsheet_id: str, range_a1: str):
    return await g_request('GET', f'{SHEETS}/spreadsheets/{spreadsheet_id}/values/{range_a1}')


@router.post('/sheets')
async def create_sheet(payload: dict):
    body = {'properties': {'title': payload.get('title', 'Untitled')}}
    return await g_request('POST', f'{SHEETS}/spreadsheets', json=body)


@router.get('/slides/{presentation_id}')
async def get_slides(presentation_id: str):
    return await g_request('GET', f'{SLIDES}/presentations/{presentation_id}')
