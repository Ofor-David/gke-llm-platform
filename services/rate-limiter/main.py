from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse
from contextlib import asynccontextmanager
import httpx
import redis.asyncio as redis
import os
import time
import logging
import hashlib


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama.inference.svc.cluster.local:11435")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis.ratelimit.svc.cluster.local:6379")
RATE_LIMIT = int(os.getenv("RATE_LIMIT", "10"))
WINDOW_SECONDS = int(os.getenv("WINDOW_SECONDS", "60"))

redis_client = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    global redis_client
    redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    yield
    # shutdown
    await redis_client.aclose()

app = FastAPI(lifespan=lifespan)

def get_client_identity(request: Request) -> str:
    # Use API key directly as the rate limit identity
    # TODO: When multi-key is implemented this switches to X-Client-Identity header
    api_key = request.headers.get("X-API-Key", "anonymous")
    # Hash it so the raw key isn't stored in Redis
    return hashlib.sha256(api_key.encode()).hexdigest()[:16]

async def check_rate_limit(identity: str) -> tuple[bool, int]:
    key = f"rate_limit:{identity}"
    now = time.time()
    window_start = now - WINDOW_SECONDS

    async with redis_client.pipeline() as pipe:
        # Sliding window : remove old entries, add current, count
        await pipe.zremrangebyscore(key, 0, window_start)
        await pipe.zadd(key, {str(now): now})
        await pipe.zcard(key)
        await pipe.expire(key, WINDOW_SECONDS)
        results = await pipe.execute()

    count = results[2]
    remaining = max(0, RATE_LIMIT - count)
    allowed = count <= RATE_LIMIT
    return allowed, remaining

@app.get("/healthz")
async def health():
    return {"status": "ok"}

@app.api_route("/{path:path}", methods=["GET", "POST", "DELETE"])
async def proxy(path: str, request: Request):
    if path == "healthz":
        return {"status": "ok"}

    identity = get_client_identity(request)
    allowed, remaining = await check_rate_limit(identity)

    if not allowed:
        logger.warning(f"Rate limit exceeded for {identity}")
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={
                "Retry-After": str(WINDOW_SECONDS),
                "X-RateLimit-Limit": str(RATE_LIMIT),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Window": str(WINDOW_SECONDS)
            }
        )

    logger.info(f"Forwarding request from {identity}, {remaining} requests remaining")

    body = await request.body()
    headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in ("host",)
    }

    async with httpx.AsyncClient(timeout=300) as client:
        resp = await client.request(
            method=request.method,
            url=f"{OLLAMA_URL}/{path}",
            content=body,
            headers=headers,
            params=request.query_params
        )

    response_headers = dict(resp.headers)
    response_headers["X-RateLimit-Limit"] = str(RATE_LIMIT)
    response_headers["X-RateLimit-Remaining"] = str(remaining)
    response_headers["X-RateLimit-Window"] = str(WINDOW_SECONDS)

    return StreamingResponse(
        content=resp.aiter_bytes(),
        status_code=resp.status_code,
        headers=response_headers,
        media_type=resp.headers.get("content-type")
    )
