from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
import time
import asyncio

class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple token-bucket rate limiter per API key (in-memory).

    Config via environment variables could be added later. This implementation
    is intentionally simple and not suitable for distributed deployments.
    """

    def __init__(self, app, calls_per_minute: int = 120, burst: int = 240):
        super().__init__(app)
        self.rate = calls_per_minute / 60.0  # tokens per second
        self.capacity = burst
        self.buckets = {}  # key -> (tokens, last_ts)
        self.lock = asyncio.Lock()

    async def dispatch(self, request: Request, call_next):
        # Identify client key. Prefer Authorization header (raw token or Bearer).
        auth = request.headers.get('authorization', '')
        key = auth.split(' ', 1)[1] if auth.lower().startswith('bearer ') else auth
        if not key:
            # No key, fallback to IP
            key = request.client.host if request.client else 'anon'

        now = time.monotonic()
        async with self.lock:
            tokens, last = self.buckets.get(key, (self.capacity, now))
            # refill
            elapsed = now - last
            tokens = min(self.capacity, tokens + elapsed * self.rate)
            if tokens < 1.0:
                # rate limit exceeded
                self.buckets[key] = (tokens, now)
                return Response(status_code=429, content='Rate limit exceeded')
            tokens -= 1.0
            self.buckets[key] = (tokens, now)
        return await call_next(request)
