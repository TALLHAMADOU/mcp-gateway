from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
import time
import asyncio
import os

# Try to use redis.asyncio when REDIS_URL is configured; otherwise fall back to
# in-memory token-bucket implementation (useful for local dev/tests).
try:
    import redis.asyncio as aioredis
except Exception:
    aioredis = None

class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiter with Redis-backed fixed-window fallback to in-memory token bucket.

    If REDIS_URL is set in the environment, this middleware uses a simple
    fixed-window counter (per-minute). Otherwise it falls back to an
    in-memory token-bucket (non-distributed).
    """

    def __init__(self, app, calls_per_minute: int = 120, burst: int = 240):
        super().__init__(app)
        self.limit = calls_per_minute
        self.capacity = burst
        self.rate = calls_per_minute / 60.0
        self.use_redis = bool(os.environ.get('REDIS_URL')) and aioredis is not None
        self.redis = None
        if self.use_redis:
            # create redis client (async)
            self.redis = aioredis.from_url(os.environ.get('REDIS_URL'))
        # in-memory fallback state
        self.buckets = {}
        self.lock = asyncio.Lock()

    async def dispatch(self, request: Request, call_next):
        auth = request.headers.get('authorization', '')
        key = auth.split(' ', 1)[1] if auth.lower().startswith('bearer ') else auth
        if not key:
            key = request.client.host if request.client else 'anon'

        if self.use_redis and self.redis:
            # fixed-window per-minute counter
            redis_key = f"rl:{key}"
            try:
                count = await self.redis.incr(redis_key)
                if count == 1:
                    await self.redis.expire(redis_key, 60)
                if count > self.limit:
                    return Response(status_code=429, content='Rate limit exceeded')
            except Exception:
                # On redis errors, fall back to in-memory logic
                pass
            return await call_next(request)

        # In-memory token-bucket (non-distributed)
        now = time.monotonic()
        async with self.lock:
            tokens, last = self.buckets.get(key, (self.capacity, now))
            elapsed = now - last
            tokens = min(self.capacity, tokens + elapsed * self.rate)
            if tokens < 1.0:
                self.buckets[key] = (tokens, now)
                return Response(status_code=429, content='Rate limit exceeded')
            tokens -= 1.0
            self.buckets[key] = (tokens, now)
        return await call_next(request)
