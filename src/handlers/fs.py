from fastapi import APIRouter, HTTPException
import os

router = APIRouter()

BASE = '.'  # operate relative to gateway working dir

@router.get('/list')
async def list_dir(path: str = '.'):
    target = os.path.normpath(os.path.join(BASE, path))
    if not os.path.exists(target):
        raise HTTPException(status_code=404, detail='path not found')
    if os.path.isfile(target):
        return {'path': path, 'type': 'file'}
    entries = []
    for name in os.listdir(target):
        p = os.path.join(target, name)
        entries.append({'name': name, 'is_dir': os.path.isdir(p)})
    return {'path': path, 'entries': entries}

@router.get('/read')
async def read_file(path: str):
    target = os.path.normpath(os.path.join(BASE, path))
    if not os.path.exists(target) or not os.path.isfile(target):
        raise HTTPException(status_code=404, detail='file not found')
    with open(target, 'rb') as f:
        data = f.read()
    return Response(content=data, media_type='application/octet-stream')
