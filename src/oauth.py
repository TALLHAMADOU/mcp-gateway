"""OAuth2 access-token providers with automatic refresh.

Cloud access tokens (Google, Microsoft Graph) expire after ~1h, which breaks
long-running gateways that were handed a static token at startup. This module
caches a token and transparently refreshes it before expiry.

Two modes per provider, decided from the environment:
  * static token only  -> used as-is (backward compatible; no refresh)
  * refresh credentials -> token is fetched/refreshed automatically

Google (refresh_token flow):
  GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REFRESH_TOKEN
Microsoft Graph (client_credentials, or refresh_token if MS_REFRESH_TOKEN set):
  MS_TENANT_ID, MS_CLIENT_ID, MS_CLIENT_SECRET [, MS_REFRESH_TOKEN]
"""
import asyncio
import os
import time

import httpx


class OAuthTokenProvider:
    """Caches an access token and refreshes it ~60s before it expires."""

    def __init__(self, name: str, static_token: str | None,
                 token_url: str | None, refresh_payload: dict | None):
        self.name = name
        self._static = static_token
        self._token_url = token_url
        self._refresh_payload = refresh_payload
        self._access: str | None = None
        self._expiry: float = 0.0
        self._lock = asyncio.Lock()

    @property
    def can_refresh(self) -> bool:
        return bool(self._token_url and self._refresh_payload)

    @property
    def configured(self) -> bool:
        return bool(self._static or self.can_refresh)

    async def get(self) -> str:
        # Static token and no refresh credentials: forward it unchanged.
        if self._static and not self.can_refresh:
            return self._static
        if not self.can_refresh:
            raise RuntimeError(f'{self.name} not configured')
        async with self._lock:
            if self._access and time.monotonic() < self._expiry:
                return self._access
            await self._refresh()
            return self._access

    async def _refresh(self) -> None:
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(self._token_url, data=self._refresh_payload)
        if r.status_code >= 400:
            raise RuntimeError(
                f'{self.name} token refresh failed: {r.status_code} {r.text}')
        data = r.json()
        self._access = data['access_token']
        # Refresh a minute early to avoid using a token that expires mid-flight.
        self._expiry = time.monotonic() + max(60, int(data.get('expires_in', 3600)) - 60)


def _google_provider() -> OAuthTokenProvider:
    cid = os.environ.get('GOOGLE_CLIENT_ID')
    csec = os.environ.get('GOOGLE_CLIENT_SECRET')
    rtok = os.environ.get('GOOGLE_REFRESH_TOKEN')
    payload = None
    if cid and csec and rtok:
        payload = {
            'client_id': cid,
            'client_secret': csec,
            'refresh_token': rtok,
            'grant_type': 'refresh_token',
        }
    return OAuthTokenProvider(
        'google', os.environ.get('GOOGLE_ACCESS_TOKEN'),
        'https://oauth2.googleapis.com/token', payload)


def _ms_provider() -> OAuthTokenProvider:
    tenant = os.environ.get('MS_TENANT_ID')
    cid = os.environ.get('MS_CLIENT_ID')
    csec = os.environ.get('MS_CLIENT_SECRET')
    rtok = os.environ.get('MS_REFRESH_TOKEN')
    token_url = None
    payload = None
    if tenant and cid and csec:
        token_url = f'https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token'
        if rtok:
            payload = {
                'client_id': cid, 'client_secret': csec, 'refresh_token': rtok,
                'grant_type': 'refresh_token',
                'scope': 'https://graph.microsoft.com/.default offline_access',
            }
        else:
            payload = {
                'client_id': cid, 'client_secret': csec,
                'grant_type': 'client_credentials',
                'scope': 'https://graph.microsoft.com/.default',
            }
    return OAuthTokenProvider(
        'ms_graph', os.environ.get('MS_GRAPH_TOKEN'), token_url, payload)


google_token = _google_provider()
ms_token = _ms_provider()
