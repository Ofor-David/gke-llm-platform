from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse
import httpx
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama.inference.svc.cluster.local:11435")
API_KEY = os.getenv("API_KEY", "")
ALLOWED_IPS = set(filter(None, os.getenv("ALLOWED_IPS", "").split(",")))


def get_client_ip(request: Request) -> str:
    """Extract real client IP, accounting for GCP load balancer X-Forwarded-For header."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """
    Authentication middleware. Order of checks:
    1. Bypass auth for health check endpoint (required for GCP LB probes)
    2. Fail closed if API_KEY is not configured
    3. IP allowlist check (skipped if ALLOWED_IPS is empty)
    4. API key check
    """

    # 1. Always allow health check through — no auth required
    if request.url.path == "/healthz":
        return await call_next(request)

    # 2. Fail closed if server is misconfigured — never allow through with no key set
    if not API_KEY:
        logger.error("API_KEY environment variable is not configured")
        return JSONResponse(
            status_code=500,
            content={"detail": "Server misconfigured: API_KEY not set"}
        )

    # 3. IP allowlist — only enforced if ALLOWED_IPS is non-empty
    client_ip = get_client_ip(request)
    if ALLOWED_IPS and client_ip not in ALLOWED_IPS:
        logger.warning(f"Rejected request from unlisted IP: {client_ip}")
        return JSONResponse(
            status_code=403,
            content={"detail": "IP not allowed"}
        )

    # 4. API key check
    api_key = request.headers.get("X-API-Key", "")
    if not api_key or api_key != API_KEY:
        logger.warning(f"Invalid or missing API key from {client_ip}")
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid or missing API key"}
        )

    logger.info(f"Authorized request from {client_ip} to {request.url.path}")
    return await call_next(request)


@app.get("/healthz")
async def health():
    """Health check endpoint for GCP load balancer probes."""
    return {"status": "ok"}


@app.api_route("/{path:path}", methods=["GET", "POST", "DELETE"])
async def proxy(path: str, request: Request):
    """
    Reverse proxy to Ollama. Streams the response back to the client.

    - Strips hop-by-hop headers that should not be forwarded
    - Forwards query params as-is
    - 300s timeout to support long-running Ollama inference requests
    """
    body = await request.body()

    # Strip headers that should not be forwarded to upstream
    excluded_request_headers = {"host", "x-api-key"}
    headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in excluded_request_headers
    }

    try:
        async with httpx.AsyncClient(timeout=300) as client:
            resp = await client.request(
                method=request.method,
                url=f"{OLLAMA_URL}/{path}",
                content=body,
                headers=headers,
                params=request.query_params
            )
    except httpx.ConnectError:
        logger.error(f"Could not connect to Ollama at {OLLAMA_URL}")
        return JSONResponse(
            status_code=502,
            content={"detail": "Could not connect to upstream Ollama service"}
        )
    except httpx.TimeoutException:
        logger.error(f"Request to Ollama timed out: {path}")
        return JSONResponse(
            status_code=504,
            content={"detail": "Upstream Ollama service timed out"}
        )
    except httpx.RequestError as e:
        logger.error(f"Unexpected error proxying to Ollama: {e}")
        return JSONResponse(
            status_code=500,
            content={"detail": "Unexpected error contacting upstream service"}
        )

    # Strip hop-by-hop headers that must not be forwarded in a streaming response
    excluded_response_headers = {"transfer-encoding", "content-encoding", "content-length"}
    clean_headers = {
        k: v for k, v in resp.headers.items()
        if k.lower() not in excluded_response_headers
    }

    return StreamingResponse(
        content=resp.aiter_bytes(),
        status_code=resp.status_code,
        headers=clean_headers,
        media_type=resp.headers.get("content-type")
    )


# TODO: multiple keys with per-key identity and rate limiting
# {
#   "keys": {
#     "key-abc123": {"identity": "team-backend", "tier": "standard"},
#     "key-xyz789": {"identity": "ci-pipeline", "tier": "standard"},
#     "key-adm000": {"identity": "admin", "tier": "unlimited"}
#   }
# }