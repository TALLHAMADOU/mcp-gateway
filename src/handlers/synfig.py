from fastapi import APIRouter, Request
import shutil

router = APIRouter()

@router.get('/health')
async def health():
    return {'status': 'ok', 'handler': 'synfig'}

@router.get('/info')
async def info():
    s = shutil.which('synfig')
    return {'installed': bool(s), 'path': s}

@router.post('/render')
async def render(request: Request):
    data = await request.json()
    cmd = data.get('cmd', 'synfig-render --input file.sif --output out.png')
    return {'ok': True, 'cmd': cmd, 'note': 'Suggested command; no execution.'}
