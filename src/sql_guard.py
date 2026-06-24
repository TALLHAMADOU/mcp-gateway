"""Shared read-only SQL validation.

This is *defense in depth*: the authoritative write guard is the database
itself (a READ ONLY transaction for Postgres, a `mode=ro` connection for
SQLite). This module rejects obviously-unsafe input early with a clean error
and blocks statement stacking.

We prefer a lightweight sqlparse-based validation when available; fallback to
regex-based checks otherwise.
"""
import re

try:
    import sqlparse
except Exception:
    sqlparse = None

# Whole-word write / DDL / session keywords. Used as a fast reject; the
# read-only DB connection is what actually prevents writes.
_FORBIDDEN = re.compile(
    r'\b(insert|update|delete|drop|alter|create|truncate|grant|revoke|'
    r'merge|copy|vacuum|reindex|call|do|set|begin|commit|rollback|'
    r'savepoint|lock|listen|notify|prepare|deallocate|attach|detach|pragma)\b',
    re.IGNORECASE,
)


def _strip_comments(sql: str) -> str:
    sql = re.sub(r'/\*.*?\*/', ' ', sql, flags=re.DOTALL)
    sql = re.sub(r'--[^\n]*', ' ', sql)
    # sqlite also supports '#' style comments
    sql = re.sub(r'#[^\n]*', ' ', sql)
    return sql


def validate_select(sql: str) -> str:
    """Return a cleaned single read-only statement, or raise ValueError.

    Uses sqlparse when available to ensure a single statement and that the
    top-level statement type is a read-only SELECT or WITH. Falls back to the
    previous heuristics otherwise.
    """
    if not isinstance(sql, str):
        raise ValueError('sql must be a string')
    cleaned = _strip_comments(sql).strip().rstrip(';').strip()
    if not cleaned:
        raise ValueError('empty SQL')

    # Prefer sqlparse for robust statement splitting and type detection
    if sqlparse:
        statements = [s for s in sqlparse.parse(cleaned) if str(s).strip()]
        if len(statements) != 1:
            raise ValueError('multiple statements are not allowed')
        st = statements[0]
        stype = st.get_type().upper()
        if stype not in ('SELECT', 'UNKNOWN') and not str(cleaned).lstrip().lower().startswith('with'):
            # sqlparse may return UNKNOWN for complex WITH queries; accept if text starts with WITH
            raise ValueError('only SELECT (or read-only WITH) queries are allowed')
        # Additional quick forbidden keyword scan
        if _FORBIDDEN.search(cleaned):
            raise ValueError('query contains forbidden / write keywords')
        return cleaned

    # Fallback heuristics
    if ';' in cleaned:
        raise ValueError('multiple statements are not allowed')
    low = cleaned.lower()
    if not (low.startswith('select') or low.startswith('with')):
        raise ValueError('only SELECT (or read-only WITH) queries are allowed')
    if _FORBIDDEN.search(cleaned):
        raise ValueError('query contains forbidden / write keywords')
    return cleaned
