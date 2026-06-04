# Stub git handler for future in-process git operations
from fastapi import APIRouter
router = APIRouter()

@router.get('/health')
async def health():
    return {'status': 'ok', 'handler': 'git'}
