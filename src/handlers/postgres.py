from fastapi import APIRouter, HTTPException, Request
from starlette.concurrency import run_in_threadpool
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool
from ..sql_guard import validate_select

router = APIRouter()

POSTGRES_DSN = os.environ.get('POSTGRES_DSN') or os.environ.get('DATABASE_URL')
PG_MIN_CONN = int(os.environ.get('PG_MIN_CONN', '1'))
PG_MAX_CONN = int(os.environ.get('PG_MAX_CONN', '5'))
PG_MAX_ROWS = int(os.environ.get('PG_MAX_ROWS', '1000'))
PG_STATEMENT_TIMEOUT_MS = int(os.environ.get('PG_STATEMENT_TIMEOUT_MS', '5000'))

_POOLS: dict = {}

@router.get('/health')
async def health():
    return {
        'status': 'ok',
        'handler': 'postgres',
        'configured': bool(POSTGRES_DSN),
        'pool_min': PG_MIN_CONN,
        'pool_max': PG_MAX_CONN,
    }


def get_pool(dsn: str):
    if dsn in _POOLS:
        return _POOLS[dsn]
    pool = ThreadedConnectionPool(PG_MIN_CONN, PG_MAX_CONN, dsn)
    _POOLS[dsn] = pool
    return pool


def _run_query(dsn: str, sql: str, params: list | None = None):
    # App-level guard (clean 400 + no statement stacking).
    sql = validate_select(sql)
    pool = get_pool(dsn)
    conn = pool.getconn()
    try:
        conn.autocommit = False
        cur = conn.cursor(cursor_factory=RealDictCursor)
        # Authoritative write guard: any write inside this tx is rejected by PG.
        cur.execute("SET TRANSACTION READ ONLY")
        # enforce statement timeout (ms)
        try:
            cur.execute(f"SET LOCAL statement_timeout = {int(PG_STATEMENT_TIMEOUT_MS)}")
        except Exception:
            # ignore if server doesn't support or SET LOCAL fails
            pass
        cur.execute(sql, params or [])
        rows = cur.fetchall()
        cols = list(rows[0].keys()) if rows else []
        truncated = False
        if len(rows) > PG_MAX_ROWS:
            rows = rows[:PG_MAX_ROWS]
            truncated = True
        conn.rollback()
        return {'columns': cols, 'rows': rows, 'truncated': truncated}
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        pool.putconn(conn)


@router.post('/query')
async def query(req: Request):
    payload = await req.json()
    sql = payload.get('sql')
    params = payload.get('params')
    dsn = payload.get('dsn') or POSTGRES_DSN
    if not sql:
        raise HTTPException(status_code=400, detail='sql is required')
    if not dsn:
        raise HTTPException(status_code=400, detail='Postgres DSN not configured (env POSTGRES_DSN or DATABASE_URL)')
    try:
        res = await run_in_threadpool(_run_query, dsn, sql, params)
        return res
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except psycopg2.OperationalError as e:
        raise HTTPException(status_code=500, detail=f'DB connection error: {e}')
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
