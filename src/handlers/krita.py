from fastapi import APIRouter, Request
import shutil

router = APIRouter()

@router.get('/health')
async def health():
    return {'status': 'ok', 'handler': 'krita'}

@router.get('/info')
async def info():
    k = shutil.which('krita')
    return {'installed': bool(k), 'path': k}

@router.post('/run')
async def run(request: Request):
    data = await request.json()
    cmd = data.get('cmd', 'krita --export')
    return {'ok': True, 'cmd': cmd, 'note': 'Suggested command only.'}
