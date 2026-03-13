from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse
import httpx
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()
client: httpx.AsyncClient | None = None

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
    if request.url.path == "/healthz":
        return await call_next(request)

    if not API_KEY:
        logger.error("API_KEY environment variable is not configured")
        return JSONResponse(
            status_code=500,
            content={"detail": "Server misconfigured: API_KEY not set"}
        )

    client_ip = get_client_ip(request)

    if ALLOWED_IPS and client_ip not in ALLOWED_IPS:
        logger.warning(f"Rejected request from unlisted IP: {client_ip}")
        return JSONResponse(
            status_code=403,
            content={"detail": "IP not allowed"}
        )

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


@app.on_event("startup")
async def startup():
    global client
    client = httpx.AsyncClient(timeout=httpx.Timeout(300, connect=10))


@app.on_event("shutdown")
async def shutdown():
    global client
    if client:
        await client.aclose()


async def stream_response(resp: httpx.Response, excluded_headers: set):
    """
    Async generator that yields chunks from the upstream response.
    Wrapped separately so exceptions during streaming are caught and logged
    rather than crashing the connection silently.
    """
    try:
        async for chunk in resp.aiter_bytes():
            yield chunk
    except httpx.RemoteProtocolError as e:
        logger.error(f"Remote protocol error while streaming: {e}")
    except httpx.ReadError as e:
        logger.error(f"Read error while streaming from Ollama: {e}")
    except Exception as e:
        logger.error(f"Unexpected error during streaming: {e}")


@app.api_route("/{path:path}", methods=["GET", "POST", "DELETE"])
async def proxy(path: str, request: Request):
    """
    Reverse proxy to Ollama. Streams the response back to the client.
    - Strips hop-by-hop headers that should not be forwarded
    - Forwards query params as-is
    - 300s timeout to support long-running Ollama inference requests
    """
    body = await request.body()

    excluded_request_headers = {"host", "x-api-key"}
    excluded_response_headers = {"transfer-encoding", "content-encoding", "content-length"}

    headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in excluded_request_headers
    }

    logger.info(f"Proxying {request.method} /{path} to {OLLAMA_URL}/{path}")

    try:
        async with client.stream(
            method=request.method,
            url=f"{OLLAMA_URL}/{path}",
            content=body,
            headers=headers,
            params=request.query_params
        ) as resp:
            logger.info(f"Ollama responded with status {resp.status_code} for /{path}")

            clean_headers = {
                k: v for k, v in resp.headers.items()
                if k.lower() not in excluded_response_headers
            }

            # If Ollama itself returned an error, read and log the body
            # then return it as-is rather than streaming an empty/broken response
            if resp.status_code >= 400:
                error_body = await resp.aread()
                logger.error(f"Ollama returned {resp.status_code} for /{path}: {error_body.decode()}")
                return JSONResponse(
                    status_code=resp.status_code,
                    content={"detail": f"Upstream error: {error_body.decode()}"}
                )

            return StreamingResponse(
                content=stream_response(resp, excluded_response_headers),
                status_code=resp.status_code,
                headers=clean_headers,
                media_type=resp.headers.get("content-type")
            )

    except httpx.ConnectError as e:
        logger.error(f"Could not connect to Ollama at {OLLAMA_URL}: {e}")
        return JSONResponse(
            status_code=502,
            content={"detail": "Could not connect to upstream Ollama service"}
        )
    except httpx.TimeoutException as e:
        logger.error(f"Request to Ollama timed out for /{path}: {e}")
        return JSONResponse(
            status_code=504,
            content={"detail": "Upstream Ollama service timed out"}
        )
    except httpx.RequestError as e:
        logger.error(f"Unexpected request error proxying to Ollama: {e}")
        return JSONResponse(
            status_code=500,
            content={"detail": "Unexpected error contacting upstream service"}
        )
    except Exception as e:
        logger.error(f"Unhandled exception in proxy for /{path}: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"}
        )