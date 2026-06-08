import pytest
from src.sql_guard import validate_select


def test_allows_plain_select():
    assert validate_select('SELECT 1') == 'SELECT 1'


def test_allows_read_only_with():
    out = validate_select('WITH x AS (SELECT 1) SELECT * FROM x')
    assert out.lower().startswith('with')


def test_strips_trailing_semicolon():
    assert validate_select('SELECT 1;') == 'SELECT 1'


def test_strips_comments():
    assert validate_select('SELECT 1 -- hello').strip() == 'SELECT 1'


@pytest.mark.parametrize('sql', [
    'DELETE FROM users',
    'UPDATE t SET a = 1',
    'DROP TABLE t',
    'INSERT INTO t VALUES (1)',
    'TRUNCATE t',
    'SELECT 1; DROP TABLE t',          # stacked
    'SELECT 1; SELECT 2',              # stacked
    'select pg_sleep(1); delete from t',
    'SELECT 1 /* */; DROP TABLE t',    # comment-hidden stack
    '',
    '   ',
])
def test_rejects_unsafe(sql):
    with pytest.raises(ValueError):
        validate_select(sql)


def test_rejects_non_string():
    with pytest.raises(ValueError):
        validate_select(None)  # type: ignore[arg-type]
