"""Health check endpoints and status monitoring."""

from fastapi import APIRouter
import os
import psutil
import asyncio
from datetime import datetime

health_router = APIRouter()

# Startup time for uptime calculation
START_TIME = datetime.utcnow()


async def check_postgres() -> dict:
    """Check PostgreSQL connectivity."""
    try:
        import asyncpg
        dsn = os.environ.get('POSTGRES_DSN')
        if not dsn:
            return {"status": "unknown", "message": "POSTGRES_DSN not set"}
        
        # Try to connect with 2s timeout
        conn = await asyncio.wait_for(
            asyncpg.connect(dsn),
            timeout=2.0
        )
        await conn.close()
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def check_redis() -> dict:
    """Check Redis connectivity."""
    try:
        import redis.asyncio
        redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379')
        
        # Try to ping with 2s timeout
        client = redis.asyncio.from_url(redis_url)
        result = await asyncio.wait_for(
            client.ping(),
            timeout=2.0
        )
        await client.close()
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@health_router.get("/health")
async def health_check():
    """Basic health check for load balancers."""
    postgres_status = await check_postgres()
    redis_status = await check_redis()
    
    # Overall status
    overall = "ok"
    if postgres_status.get("status") == "error":
        overall = "degraded"
    if redis_status.get("status") == "error":
        overall = "degraded"
    
    return {
        "status": overall,
        "timestamp": datetime.utcnow().isoformat(),
        "postgres": postgres_status,
        "redis": redis_status
    }


@health_router.get("/health/ready")
async def readiness_check():
    """Kubernetes readiness probe."""
    uptime_seconds = (datetime.utcnow() - START_TIME).total_seconds()
    
    postgres_status = await check_postgres()
    redis_status = await check_redis()
    
    # Ready if we can connect to both
    ready = (
        postgres_status.get("status") != "error" and
        redis_status.get("status") != "error"
    )
    
    return {
        "ready": ready,
        "version": os.environ.get('VERSION', 'dev'),
        "uptime_seconds": int(uptime_seconds),
        "timestamp": datetime.utcnow().isoformat(),
        "dependencies": {
            "postgres": postgres_status,
            "redis": redis_status
        }
    }


@health_router.get("/health/live")
async def liveness_check():
    """Kubernetes liveness probe."""
    return {
        "alive": True,
        "timestamp": datetime.utcnow().isoformat()
    }
