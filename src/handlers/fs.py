from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
import os

router = APIRouter()

# Operate relative to the gateway working dir. FS_ROOT can override the
# sandbox root; all resolved paths must stay inside it.
BASE = os.path.realpath(os.environ.get('FS_ROOT', '.'))


def _resolve(path: str) -> str:
    """Resolve `path` inside BASE, rejecting traversal and absolute escapes."""
    target = os.path.realpath(os.path.join(BASE, path))
    if target != BASE and not target.startswith(BASE + os.sep):
        raise HTTPException(status_code=403, detail='path escapes sandbox root')
    return target


@router.get('/list')
async def list_dir(path: str = '.'):
    target = _resolve(path)
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
    target = _resolve(path)
    if not os.path.exists(target) or not os.path.isfile(target):
        raise HTTPException(status_code=404, detail='file not found')
    with open(target, 'rb') as f:
        data = f.read()
    return Response(content=data, media_type='application/octet-stream')
