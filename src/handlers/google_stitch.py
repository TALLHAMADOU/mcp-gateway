from fastapi import APIRouter
import os

router = APIRouter()

@router.get('/health')
async def health():
    # 'Google Stitch' ambiguous; placeholder handler
    return {'status': 'ok', 'handler': 'google_stitch', 'note': 'Placeholder — clarify exact product/service.'}

@router.get('/info')
async def info():
    return {'available': False, 'note': 'Clarify the exact Google product (Stitch? Photos?): implementation pending.'}
