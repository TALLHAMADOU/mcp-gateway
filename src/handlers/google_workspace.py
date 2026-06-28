"""Google Workspace proxy — Drive / Docs / Sheets / Slides.

Auth: an OAuth2 access token with the right scopes, supplied via
`GOOGLE_ACCESS_TOKEN` (same env-token pattern as the github/notion handlers).
Mint it from a service account or the OAuth playground; the gateway only
forwards it as a bearer token.
"""
from fastapi import APIRouter, HTTPException
import httpx

from ..oauth import google_token

router = APIRouter()

DRIVE = 'https://www.googleapis.com/drive/v3'
DOCS = 'https://docs.googleapis.com/v1'
SHEETS = 'https://sheets.googleapis.com/v4'
SLIDES = 'https://slides.googleapis.com/v1'


async def _auth_headers():
    try:
        token = await google_token.get()
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}


async def g_request(method: str, url: str, *, params=None, json=None):
    headers = await _auth_headers()
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.request(method, url, headers=headers, params=params, json=json)
        if r.status_code >= 400:
            raise HTTPException(status_code=r.status_code, detail=r.text)
        return r.json()


@router.get('/health')
async def health():
    return {'status': 'ok', 'handler': 'google_workspace', 'configured': google_token.configured}


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
