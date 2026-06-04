from fastapi import APIRouter, HTTPException
import httpx
import os

router = APIRouter()

CDP_HOST = os.environ.get('CHROME_DEBUG_HOST', 'http://localhost:9222')

@router.get('/health')
async def health():
    return {'status': 'ok', 'handler': 'chrome_devtools', 'configured': True}

@router.get('/targets')
async def targets():
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{CDP_HOST}/json")
            return r.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get('/target/{id_or_index}')
async def target(id_or_index: str):
    # Return a target object by id or index
    t = None
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{CDP_HOST}/json")
            arr = r.json()
            # try id match
            for item in arr:
                if item.get('id') == id_or_index or item.get('webSocketDebuggerUrl', '').endswith(id_or_index):
                    t = item
                    break
            if t is None:
                # try numeric index
                idx = int(id_or_index)
                t = arr[idx]
            return t
    except ValueError:
        raise HTTPException(status_code=404, detail='target not found')
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Note: full websocket proxy not implemented in MVP. Use direct websocket URL from target.webSocketDebuggerUrl
