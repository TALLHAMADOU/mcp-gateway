"""Shared read-only SQL validation.

This is *defense in depth*: the authoritative write guard is the database
itself (a READ ONLY transaction for Postgres, a `mode=ro` connection for
SQLite). This module rejects obviously-unsafe input early with a clean error
and blocks statement stacking.
"""
import re

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
    return sql


def validate_select(sql: str) -> str:
    """Return a cleaned single read-only statement, or raise ValueError."""
    if not isinstance(sql, str):
        raise ValueError('sql must be a string')
    cleaned = _strip_comments(sql).strip().rstrip(';').strip()
    if not cleaned:
        raise ValueError('empty SQL')
    if ';' in cleaned:
        raise ValueError('multiple statements are not allowed')
    low = cleaned.lower()
    if not (low.startswith('select') or low.startswith('with')):
        raise ValueError('only SELECT (or read-only WITH) queries are allowed')
    if _FORBIDDEN.search(cleaned):
        raise ValueError('query contains forbidden / write keywords')
    return cleaned
