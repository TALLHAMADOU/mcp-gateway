from fastapi import APIRouter, HTTPException, Request
import shutil

router = APIRouter()

@router.get('/health')
async def health():
    return {'status': 'ok', 'handler': 'gimp'}

@router.get('/info')
async def info():
    g = shutil.which('gimp') or shutil.which('gimp-2.10')
    return {'installed': bool(g), 'path': g}

@router.post('/run')
async def run(request: Request):
    data = await request.json()
    cmd = data.get('cmd', 'gimp --batch-interpreter')
    return {'ok': True, 'cmd': cmd, 'note': 'MVP returns suggested command. Execution not performed.'}
