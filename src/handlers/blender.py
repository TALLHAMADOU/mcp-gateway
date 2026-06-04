from fastapi import APIRouter, Request
import shutil, os

router = APIRouter()

@router.get('/health')
async def health():
    return {'status': 'ok', 'handler': 'blender'}

@router.get('/info')
async def info():
    b = shutil.which('blender')
    return {'installed': bool(b), 'path': b}

@router.post('/run-script')
async def run_script(request: Request):
    data = await request.json()
    script = data.get('script')
    # For MVP: return the command that would be run
    blender = shutil.which('blender') or '/usr/bin/blender'
    cmd = f"{blender} --background --python {script}"
    return {'ok': True, 'cmd': cmd, 'note': 'MVP returns suggested command. Execute with caution.'}
