from fastapi import APIRouter, HTTPException, Request
from starlette.concurrency import run_in_threadpool
import sqlite3
import os
from ..sql_guard import validate_select

router = APIRouter()

@router.get('/health')
async def health():
    return {'status': 'ok', 'handler': 'db', 'supported': ['sqlite']}

def _run_sqlite_query(db_path: str, sql: str, params: list | None = None):
    if not os.path.exists(db_path):
        raise FileNotFoundError('db file not found')
    # Authoritative write guard: read-only connection rejects any write.
    conn = sqlite3.connect(f'file:{db_path}?mode=ro', uri=True)
    try:
        cur = conn.cursor()
        cur.execute(sql, params or [])
        cols = [d[0] for d in cur.description] if cur.description else []
        rows = cur.fetchall()
        return {'columns': cols, 'rows': rows}
    finally:
        conn.close()

@router.post('/sqlite/query')
async def sqlite_query(payload: dict):
    db_path = payload.get('db_path')
    sql = payload.get('sql')
    if not db_path or not sql:
        raise HTTPException(status_code=400, detail='db_path and sql required')
    # App-level guard (clean 400 + no statement stacking).
    try:
        sql = validate_select(sql)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    try:
        res = await run_in_threadpool(_run_sqlite_query, db_path, sql, payload.get('params'))
        return res
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
