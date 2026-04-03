from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse
from prometheus_client import Counter, Histogram, Gauge, make_asgi_app
import httpx
import json
import asyncio
import time
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
INSTANCE_COST_PER_HOUR = float(os.getenv("INSTANCE_COST_PER_HOUR", "0.031"))
METRICS_PORT = int(os.getenv("METRICS_PORT", "8080"))
PROXY_PORT = int(os.getenv("PROXY_PORT", "11435"))

# --- Metrics ---
requests_total = Counter(
    'ollama_requests_total',
    'Total requests to Ollama',
    ['model', 'endpoint']
)
request_duration = Histogram(
    'ollama_request_duration_seconds',
    'Request duration in seconds',
    ['model', 'endpoint'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0]
)
prompt_tokens = Counter(
    'ollama_prompt_tokens_total',
    'Total prompt tokens evaluated',
    ['model']
)
generated_tokens = Counter(
    'ollama_generated_tokens_total',
    'Total tokens generated',
    ['model']
)
model_loaded = Gauge(
    'ollama_model_loaded',
    'Whether model is loaded in memory',
    ['model']
)
queue_depth = Gauge(
    'ollama_queue_depth',
    'In-flight requests used by KEDA'
)
cost_per_hour = Gauge(
    'ollama_estimated_cost_per_hour_usd',
    'Estimated cost per hour'
)

# --- App ---
active_requests = 0
active_requests_lock = asyncio.Lock()
@asynccontextmanager
async def lifespan(app: FastAPI):
    # everything before yield runs on startup
    global client
    client = httpx.AsyncClient(timeout=httpx.Timeout(300, connect=10))
    asyncio.create_task(poll_model_status())
    
    yield  # app is running here
    
    # everything after yield runs on shutdown
    if client:
        await client.aclose()
client: httpx.AsyncClient | None = None
app = FastAPI(lifespan=lifespan)


async def stream_and_record_metrics(resp: httpx.Response, model_hint: str, endpoint: str, start: float):
    """
    Streams response chunks to the client while collecting the full body
    in the background to extract Ollama metrics after completion.
    
    - Yields chunks immediately as they arrive (true streaming)
    - After stream ends, parses the final JSON chunk for token counts
    - Records duration, token counts, and request totals to Prometheus
    """
    full_body = b""
    try:
        async for chunk in resp.aiter_bytes():
            full_body += chunk
            yield chunk
    except httpx.RemoteProtocolError as e:
        logger.error(f"Remote protocol error while streaming: {e}")
    except httpx.ReadError as e:
        logger.error(f"Read error while streaming from Ollama: {e}")
    except Exception as e:
        logger.error(f"Unexpected error during streaming: {e}")
    finally:
        duration = time.time() - start
        await resp.asclose()

        # Parse metrics from response body
        # For streaming responses, Ollama sends one JSON object per line.
        # The last line contains the final stats (eval_count, prompt_eval_count etc.)
        try:
            # Try parsing as single JSON first (stream=false)
            data = json.loads(full_body)
            model = data.get("model", model_hint)
            endpoint_label = endpoint.split("/")[-1]

            requests_total.labels(model=model, endpoint=endpoint_label).inc()
            request_duration.labels(model=model, endpoint=endpoint_label).observe(duration)

            if "prompt_eval_count" in data:
                prompt_tokens.labels(model=model).inc(data["prompt_eval_count"])
            if "eval_count" in data:
                generated_tokens.labels(model=model).inc(data["eval_count"])

            logger.info(f"Completed /{endpoint_label} model={model} duration={duration:.2f}s")

        except json.JSONDecodeError:
            # Streaming response — parse line by line, last line has the stats
            try:
                lines = full_body.decode().strip().split("\n")
                last_line = json.loads(lines[-1])
                model = last_line.get("model", model_hint)
                endpoint_label = endpoint.split("/")[-1]

                requests_total.labels(model=model, endpoint=endpoint_label).inc()
                request_duration.labels(model=model, endpoint=endpoint_label).observe(duration)

                if "prompt_eval_count" in last_line:
                    prompt_tokens.labels(model=model).inc(last_line["prompt_eval_count"])
                if "eval_count" in last_line:
                    generated_tokens.labels(model=model).inc(last_line["eval_count"])

                logger.info(f"Completed /{endpoint_label} model={model} duration={duration:.2f}s")

            except Exception as e:
                logger.warning(f"Could not parse metrics from response: {e}")

        except Exception as e:
            logger.warning(f"Could not parse metrics from response: {e}")


@app.middleware("http")
async def track_queue_depth(request: Request, call_next):
    """Track active in-flight requests for KEDA autoscaling."""
    global active_requests
    async with active_requests_lock:
        active_requests += 1
        queue_depth.set(active_requests)
    try:
        return await call_next(request)
    finally:
        async with active_requests_lock:
            active_requests -= 1
            queue_depth.set(active_requests)


@app.get("/healthz")
async def health():
    return {"status": "ok"}

# Mount Prometheus metrics endpoint on /metrics
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

@app.api_route("/{path:path}", methods=["GET", "POST", "DELETE"])
async def proxy(path: str, request: Request):
    """
    Async reverse proxy to Ollama with metrics collection.
    Uses client.send(stream=True) to keep the connection open for the
    full duration of the StreamingResponse — fixes the 'stream closed'
    error caused by async with context manager exiting on return.
    """
    if path == "metrics" or path.startswith("metrics/"):
        return JSONResponse(status_code=404, content={"detail": "Not found"})
    
    body = await request.body()
    start = time.time()

    excluded_request_headers = {"host"}
    excluded_response_headers = {"transfer-encoding", "content-encoding", "content-length"}

    headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in excluded_request_headers
    }

    model_hint = "unknown"
    try:
        model_hint = json.loads(body).get("model", "unknown")
    except Exception:
        pass

    logger.info(f"Proxying {request.method} /{path} model={model_hint}")

    # Build and send the request with stream=True
    # This returns response headers immediately without reading the body,
    # so we can check status and set it on StreamingResponse correctly
    try:
        req = client.build_request(
            method=request.method,
            url=f"{OLLAMA_URL}/{path}",
            content=body,
            headers=headers,
            params=request.query_params
        )
        resp = await client.send(req, stream=True)
    except httpx.ConnectError as e:
        logger.error(f"Could not connect to Ollama at {OLLAMA_URL}: {e}")
        return JSONResponse(status_code=502, content={"detail": "Could not connect to upstream Ollama service"})
    except httpx.TimeoutException as e:
        logger.error(f"Request to Ollama timed out for /{path}: {e}")
        return JSONResponse(status_code=504, content={"detail": "Upstream Ollama service timed out"})
    except httpx.RequestError as e:
        logger.error(f"Unexpected request error proxying to Ollama: {e}")
        return JSONResponse(status_code=500, content={"detail": "Unexpected error contacting upstream service"})
    except Exception as e:
        logger.error(f"Unhandled exception in proxy for /{path}: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    logger.info(f"Ollama responded with status {resp.status_code} for /{path}")

    # Handle upstream errors before streaming
    if resp.status_code >= 400:
        error_body = await resp.aread()
        await resp.aclose()
        logger.error(f"Ollama returned {resp.status_code} for /{path}: {error_body.decode()}")
        return JSONResponse(
            status_code=resp.status_code,
            content={"detail": f"Upstream error: {error_body.decode()}"}
        )

    clean_headers = {
        k: v for k, v in resp.headers.items()
        if k.lower() not in excluded_response_headers
    }

    async def stream_and_close():
        """
        Generator that streams chunks and closes the response when done.
        Defined inside proxy so it closes over resp — keeping the connection
        alive until the generator is fully consumed by StreamingResponse.
        """
        full_body = b""
        try:
            async for chunk in resp.aiter_bytes():
                full_body += chunk
                yield chunk
        except httpx.RemoteProtocolError as e:
            logger.error(f"Remote protocol error while streaming: {e}")
        except httpx.ReadError as e:
            logger.error(f"Read error while streaming from Ollama: {e}")
        except Exception as e:
            logger.error(f"Unexpected error during streaming: {e}", exc_info=True)
        finally:
            # Always close the response connection
            await resp.aclose()

            # Record metrics after stream completes
            duration = time.time() - start
            endpoint_label = path.split("/")[-1]
            try:
                data = json.loads(full_body)
                model = data.get("model", model_hint)
                requests_total.labels(model=model, endpoint=endpoint_label).inc()
                request_duration.labels(model=model, endpoint=endpoint_label).observe(duration)
                if "prompt_eval_count" in data:
                    prompt_tokens.labels(model=model).inc(data["prompt_eval_count"])
                if "eval_count" in data:
                    generated_tokens.labels(model=model).inc(data["eval_count"])
                logger.info(f"Completed /{endpoint_label} model={model} duration={duration:.2f}s")
            except json.JSONDecodeError:
                try:
                    lines = full_body.decode().strip().split("\n")
                    last_line = json.loads(lines[-1])
                    model = last_line.get("model", model_hint)
                    requests_total.labels(model=model, endpoint=endpoint_label).inc()
                    request_duration.labels(model=model, endpoint=endpoint_label).observe(duration)
                    if "prompt_eval_count" in last_line:
                        prompt_tokens.labels(model=model).inc(last_line["prompt_eval_count"])
                    if "eval_count" in last_line:
                        generated_tokens.labels(model=model).inc(last_line["eval_count"])
                    logger.info(f"Completed /{endpoint_label} model={model} duration={duration:.2f}s")
                except Exception as e:
                    logger.warning(f"Could not parse metrics from response: {e}")
            except Exception as e:
                logger.warning(f"Could not parse metrics from response: {e}")

    return StreamingResponse(
        content=stream_and_close(),
        status_code=resp.status_code,
        headers=clean_headers,
        media_type=resp.headers.get("content-type")
    )

async def poll_model_status():
    """
    Background task that polls Ollama every 15s to check which models
    are loaded in memory and updates cost/model gauges accordingly.
    """
    async with httpx.AsyncClient(timeout=5) as client:
        while True:
            try:
                resp = await client.get(f"{OLLAMA_URL}/api/ps")
                models = resp.json().get("models", [])
                if models:
                    for m in models:
                        model_loaded.labels(model=m["name"]).set(1)
                    cost_per_hour.set(INSTANCE_COST_PER_HOUR)
                else:
                    model_loaded.labels(model="none").set(0)
                    cost_per_hour.set(0)
            except Exception as e:
                logger.warning(f"Could not poll Ollama model status: {e}")
            await asyncio.sleep(15)

