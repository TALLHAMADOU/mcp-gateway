from fastapi import APIRouter, HTTPException, Request
from starlette.concurrency import run_in_threadpool
import sqlite3
import os

router = APIRouter()

@router.get('/health')
async def health():
    return {'status': 'ok', 'handler': 'db', 'supported': ['sqlite']}

def _run_sqlite_query(db_path: str, sql: str, params: list | None = None):
    if not os.path.exists(db_path):
        raise FileNotFoundError('db file not found')
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(sql, params or [])
    cols = [d[0] for d in cur.description] if cur.description else []
    rows = cur.fetchall()
    conn.close()
    return {'columns': cols, 'rows': rows}

@router.post('/sqlite/query')
async def sqlite_query(payload: dict):
    db_path = payload.get('db_path')
    sql = payload.get('sql')
    if not db_path or not sql:
        raise HTTPException(status_code=400, detail='db_path and sql required')
    # Safety: only allow SELECT queries in MVP
    if not sql.strip().lower().startswith('select'):
        raise HTTPException(status_code=400, detail='Only SELECT queries are allowed in MVP')
    try:
        res = await run_in_threadpool(_run_sqlite_query, db_path, sql, payload.get('params'))
        return res
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
