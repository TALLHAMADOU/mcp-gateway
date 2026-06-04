from fastapi import APIRouter, HTTPException, Request
import shutil, os

router = APIRouter()

@router.get('/health')
async def health():
    return {'status': 'ok', 'handler': 'inkscape'}

@router.get('/info')
async def info():
    ink = shutil.which('inkscape')
    return {'installed': bool(ink), 'path': ink}

@router.post('/run')
async def run(request: Request):
    data = await request.json()
    # For safety: do not execute arbitrary commands in MVP. Return suggested command
    filepath = data.get('file')
    action = data.get('action', 'export-png')
    cmd = f"inkscape --export-type=png {filepath}"
    return {'ok': True, 'cmd': cmd, 'note': 'MVP returns suggested command. Implement execution carefully.'}
