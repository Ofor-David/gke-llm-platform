from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse
import httpx
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama.inference.svc.cluster.local:11434")
API_KEY = os.getenv("API_KEY", "")
ALLOWED_IPS = set(filter(None, os.getenv("ALLOWED_IPS", "").split(",")))

def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    # Health check bypass: needed for GCP load balancer probes
    if request.url.path == "/healthz":
        return await call_next(request)

    # IP allowlist check
    client_ip = get_client_ip(request)
    if ALLOWED_IPS and client_ip not in ALLOWED_IPS:
        logger.warning(f"Rejected IP: {client_ip}")
        raise HTTPException(status_code=403, detail="IP not allowed")

    # API key check
    api_key = request.headers.get("X-API-Key", "")
    if not api_key or api_key != API_KEY:
        logger.warning(f"Invalid API key from {client_ip}")
        raise HTTPException(status_code=401, detail="Invalid API key")

    logger.info(f"Authorized request from {client_ip} to {request.url.path}")
    return await call_next(request)

@app.get("/healthz")
async def health():
    return {"status": "ok"}

@app.api_route("/{path:path}", methods=["GET", "POST", "DELETE"])
async def proxy(path: str, request: Request):
    body = await request.body()
    headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in ("host", "x-api-key")
    }

    async with httpx.AsyncClient(timeout=300) as client:
        resp = await client.request(
            method=request.method,
            url=f"{OLLAMA_URL}/{path}",
            content=body,
            headers=headers,
            params=request.query_params
        )

    return StreamingResponse(
        content=resp.aiter_bytes(),
        status_code=resp.status_code,
        headers=dict(resp.headers),
        media_type=resp.headers.get("content-type")
    )

# TODO: multiple keys with per-key identity
""" {
  "keys": {
    "key-abc123": {"identity": "team-backend", "tier": "standard"},
    "key-xyz789": {"identity": "ci-pipeline", "tier": "standard"},
    "key-adm000": {"identity": "admin", "tier": "unlimited"}
  }
} """