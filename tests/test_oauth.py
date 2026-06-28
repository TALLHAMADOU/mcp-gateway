import asyncio
import pytest
from src import oauth


def _client_factory(resp, calls):
    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, data=None):
            calls['n'] += 1
            return resp
    return lambda *a, **k: _Client()


class _Resp:
    def __init__(self, status, payload):
        self.status_code = status
        self.text = str(payload)
        self._payload = payload

    def json(self):
        return self._payload


# --- token modes ------------------------------------------------------------

def test_static_token_is_forwarded_without_refresh():
    p = oauth.OAuthTokenProvider('x', 'static-abc', None, None)
    assert p.configured and not p.can_refresh
    assert asyncio.run(p.get()) == 'static-abc'


def test_unconfigured_provider_raises():
    p = oauth.OAuthTokenProvider('x', None, None, None)
    assert not p.configured
    with pytest.raises(RuntimeError):
        asyncio.run(p.get())


def test_refresh_is_cached_until_expiry(monkeypatch):
    calls = {'n': 0}
    monkeypatch.setattr(oauth.httpx, 'AsyncClient',
                        _client_factory(_Resp(200, {'access_token': 'tok1', 'expires_in': 3600}), calls))
    p = oauth.OAuthTokenProvider('x', None, 'https://token', {'grant_type': 'refresh_token'})

    async def scenario():
        first = await p.get()
        cached = await p.get()           # within expiry -> no second call
        p._expiry = 0                    # force expiry
        refreshed = await p.get()        # triggers a second refresh
        return first, cached, refreshed

    first, cached, refreshed = asyncio.run(scenario())
    assert first == cached == refreshed == 'tok1'
    assert calls['n'] == 2


def test_refresh_failure_raises(monkeypatch):
    calls = {'n': 0}
    monkeypatch.setattr(oauth.httpx, 'AsyncClient',
                        _client_factory(_Resp(400, {'error': 'invalid_grant'}), calls))
    p = oauth.OAuthTokenProvider('x', None, 'https://token', {'grant_type': 'refresh_token'})
    with pytest.raises(RuntimeError):
        asyncio.run(p.get())


# --- provider construction from env -----------------------------------------

def test_google_provider_builds_refresh_payload(monkeypatch):
    for k in ('GOOGLE_CLIENT_ID', 'GOOGLE_CLIENT_SECRET', 'GOOGLE_REFRESH_TOKEN'):
        monkeypatch.setenv(k, 'v')
    p = oauth._google_provider()
    assert p.can_refresh
    assert p._refresh_payload['grant_type'] == 'refresh_token'


def test_ms_provider_defaults_to_client_credentials(monkeypatch):
    monkeypatch.setenv('MS_TENANT_ID', 't')
    monkeypatch.setenv('MS_CLIENT_ID', 'c')
    monkeypatch.setenv('MS_CLIENT_SECRET', 's')
    monkeypatch.delenv('MS_REFRESH_TOKEN', raising=False)
    p = oauth._ms_provider()
    assert p.can_refresh
    assert p._refresh_payload['grant_type'] == 'client_credentials'
