from fastapi import APIRouter, HTTPException, Request, Response
import os, httpx

router = APIRouter()
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')
GITHUB_API = 'https://api.github.com'

@router.get('/health')
async def health():
    return {'status': 'ok', 'handler': 'github', 'configured': bool(GITHUB_TOKEN)}

async def gh_get(path: str, params: dict | None = None):
    headers = {'Accept': 'application/vnd.github+json'}
    if GITHUB_TOKEN:
        headers['Authorization'] = f'token {GITHUB_TOKEN}'
    url = f"{GITHUB_API}/{path.lstrip('/') }"
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers=headers, params=params)
        return r

@router.get('/repos/{owner}/{repo}')
async def repo_info(owner: str, repo: str):
    r = await gh_get(f'repos/{owner}/{repo}')
    return Response(content=r.content, status_code=r.status_code, media_type=r.headers.get('content-type'))

@router.get('/repos/{owner}/{repo}/issues')
async def repo_issues(owner: str, repo: str, state: str = 'open'):
    r = await gh_get(f'repos/{owner}/{repo}/issues', params={'state': state})
    return Response(content=r.content, status_code=r.status_code, media_type=r.headers.get('content-type'))

@router.get('/repos/{owner}/{repo}/pulls')
async def repo_pulls(owner: str, repo: str, state: str = 'open'):
    r = await gh_get(f'repos/{owner}/{repo}/pulls', params={'state': state})
    return Response(content=r.content, status_code=r.status_code, media_type=r.headers.get('content-type'))
