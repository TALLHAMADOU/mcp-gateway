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

# metrics (prometheus)
try:
    from .metrics import rate_limit_hits
except Exception:
    rate_limit_hits = None

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
            # Redis-backed token-bucket implemented atomically via EVAL (Lua).
            redis_key = f"rl:{key}"
            try:
                now_ms = int(time.time() * 1000)
                capacity = int(self.capacity)
                # rate per millisecond (tokens per ms)
                rate_per_ms = float(self.rate) / 1000.0
                lua = r"""
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local rate = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local requested = tonumber(ARGV[4])
local data = redis.call('HMGET', key, 'tokens', 'ts')
local tokens = tonumber(data[1])
local ts = tonumber(data[2])
if not tokens or not ts then
  tokens = capacity
  ts = now
end
local delta = (now - ts)
local new_tokens = tokens + delta * rate
if new_tokens > capacity then new_tokens = capacity end
if new_tokens < requested then
  redis.call('HMSET', key, 'tokens', new_tokens, 'ts', now)
  redis.call('PEXPIRE', key, 60000)
  return 0
else
  new_tokens = new_tokens - requested
  redis.call('HMSET', key, 'tokens', new_tokens, 'ts', now)
  redis.call('PEXPIRE', key, 60000)
  return 1
end
"""
                ok = await self.redis.eval(lua, 1, redis_key, str(capacity), str(rate_per_ms), str(now_ms), '1')
                if int(ok) == 0:
                    if rate_limit_hits:
                        try:
                            rate_limit_hits.inc()
                        except Exception:
                            pass
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
