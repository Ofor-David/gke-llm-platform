from prometheus_client import start_http_server, Counter, Histogram, Gauge
import requests
import json
import threading
import time
import os
from http.server import HTTPServer, BaseHTTPRequestHandler

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
INSTANCE_COST_PER_HOUR = float(os.getenv("INSTANCE_COST_PER_HOUR", "0.031"))
METRICS_PORT = int(os.getenv("METRICS_PORT", "8080"))
PROXY_PORT = int(os.getenv("PROXY_PORT", "11435"))

# Metrics
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

active_requests = 0
active_requests_lock = threading.Lock()

class ProxyHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        global active_requests
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)

        with active_requests_lock:
            active_requests += 1
            queue_depth.set(active_requests)

        start = time.time()
        try:
            resp = requests.post(
                f"{OLLAMA_URL}{self.path}",
                data=body,
                headers=dict(self.headers),
                stream=True,
                timeout=300
            )

            self.send_response(resp.status_code)
            for k, v in resp.headers.items():
                self.send_header(k, v)
            self.end_headers()

            # Collect full response to extract metrics
            full_body = b""
            for chunk in resp.iter_content(chunk_size=None):
                self.wfile.write(chunk)
                full_body += chunk

            duration = time.time() - start

            # Parse metrics from response
            try:
                data = json.loads(full_body)
                model = data.get("model", "unknown")
                endpoint = self.path.split("/")[-1]

                requests_total.labels(model=model, endpoint=endpoint).inc()
                request_duration.labels(model=model, endpoint=endpoint).observe(duration)

                if "prompt_eval_count" in data:
                    prompt_tokens.labels(model=model).inc(data["prompt_eval_count"])
                if "eval_count" in data:
                    generated_tokens.labels(model=model).inc(data["eval_count"])

            except Exception:
                pass

        except Exception as e:
            self.send_response(502)
            self.end_headers()
            self.wfile.write(str(e).encode())
        finally:
            with active_requests_lock:
                active_requests -= 1
                queue_depth.set(active_requests)

    def do_GET(self):
        resp = requests.get(f"{OLLAMA_URL}{self.path}", timeout=10)
        self.send_response(resp.status_code)
        self.end_headers()
        self.wfile.write(resp.content)

    def log_message(self, format, *args):
        pass  # suppress default HTTP logs

def poll_model_status():
    while True:
        try:
            resp = requests.get(f"{OLLAMA_URL}/api/ps", timeout=5)
            models = resp.json().get("models", [])
            if models:
                for m in models:
                    model_loaded.labels(model=m["name"]).set(1)
                cost_per_hour.set(INSTANCE_COST_PER_HOUR)
            else:
                model_loaded.labels(model="none").set(0)
                cost_per_hour.set(0)
        except Exception:
            pass
        time.sleep(15)

if __name__ == "__main__":
    # Start Prometheus metrics server
    start_http_server(METRICS_PORT)
    print(f"Metrics server on :{METRICS_PORT}")

    # Start model status poller
    threading.Thread(target=poll_model_status, daemon=True).start()

    # Start proxy server
    print(f"Proxy server on :{PROXY_PORT}")
    HTTPServer(("0.0.0.0", PROXY_PORT), ProxyHandler).serve_forever()