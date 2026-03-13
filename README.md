# GKE LLM Inference Platform

A production-grade, self-hosted AI coding assistant platform built on Google Kubernetes Engine. It serves the Qwen2.5-coder 1.5B language model via Ollama, exposing a secure, rate-limited, observable REST API over the public internet.

## Why This Exists

Companies that write proprietary software face a dilemma with AI coding tools: they're productive but require sending source code to third-party APIs. This platform keeps your code within your own infrastructure, satisfies GDPR requirements by keeping data in the EU, and gives your team full control over model selection, access, cost, and observability.

## Who Uses It

- **Developers**: send code prompts from editors, CLI tools, or internal tooling
- **CI/CD pipelines**: automated code review or documentation generation
- **Platform team**: manages access, monitors usage, controls cost

## Request Flow

Every API request flows through:

```
Internet → GKE Gateway → Auth Service → Rate Limiter → Metrics Exporter → Ollama
```

1. **Gateway**: GCP L7 Global Load Balancer with TLS via Let's Encrypt
2. **Auth Service**: validates API keys, enforces IP allowlist
3. **Rate Limiter**: 10 requests/minute per key using Redis
4. **Metrics Exporter**: extracts token counts and durations, exposes to Prometheus
5. **Ollama**: serves Qwen2.5-coder 1.5B on CPU

## Architecture
### High Level Architecture
![Project High Level Architecture](./llm-platform-archi.png)
### Infrastructure
- **GCP Region**: europe-west4 (Amsterdam): GDPR compliance, low latency for Western Europe
- **GKE Cluster**: Private cluster with two node pools
  - System pool: for platform services (ArgoCD, Prometheus, cert-manager, etc.)
  - Inference pool: Spot instances for Ollama (60-91% discount)
- **Networking**: VPC with subnets for GKE and bastion, Cloud NAT for egress, Cloud DNS with DNSSEC
- **Bastion**: Jump host for private cluster access via IAP tunneling

### Application Services
- **auth-service**: FastAPI, validates API keys from GCP Secret Manager, enforces IP allowlist
- **rate-limiter**: FastAPI + Redis, sliding window per-client rate limiting
- **metrics-exporter**: Python reverse proxy, extracts LLM metrics from Ollama responses
- **ollama**: Runs Qwen2.5-coder 1.5B, model weights on Regional SSD PVC

## Security (Defence in Depth)

Eight independent layers: each assumes the ones above may be compromised:

1. **Network perimeter**: only ports 80/443 exposed, GCP health checks whitelisted, GKE control plane via master authorized networks only
2. **TLS termination**: Let's Encrypt via DNS-01 challenge (domain proven via Cloud DNS TXT record), cert-manager handles auto-renewal
3. **Authentication**: API keys stored in GCP Secret Manager, synced via External Secrets Operator using Workload Identity (no static credentials)
4. **IP allowlist**: valid API keys rejected from unexpected IPs: stolen keys useless without network access
5. **Rate limiting**: 10 req/min per key prevents cost abuse from compromised keys or runaway scripts
6. **Service mesh mTLS**: Linkerd auto-injects sidecars at namespace level, all pod-to-pod traffic encrypted and mutually authenticated
7. **Network policies**: inference namespace defaults to deny, explicit allow for rate-limiter → metrics-exporter and Prometheus → metrics-exporter
8. **Image scanning**: Trivy fails builds on CRITICAL/HIGH CVEs, Artifact Registry scans continuously

## Autoscaling

- **KEDA** scales Ollama pods based on custom Prometheus metric `ollama_queue_depth`: adds second pod when queue exceeds 3 concurrent requests
- **Node pool** scales from 1 to 2 nodes to accommodate new pods
- **Scale to zero** during inactivity: platform team keeps one warm node to avoid 5-6 minute cold start
- Inference node pool uses spot instances: if reclaimed, GKE automatically replaces and pod reschedules

## Observability

- **kube-prometheus-stack**: Prometheus, Grafana, Alertmanager, node-exporter, kube-state-metrics
- **Metrics exporter sidecar**: Intercepts every Ollama request/response, extracts:
  - Token counts (prompt, completion, total)
  - Durations (prompt eval, generation)
  - Queue depth for KEDA scaling
  - Cost per hour (instance price × pod count via recording rules)
- **Three custom Grafana dashboards**:
  - Cluster Overview: node CPU, memory, pod health
  - Inference Metrics: request rate, p50/p95/p99 latency, error rate, queue depth
  - LLM-Specific: tokens/sec, prompt eval time, generation time, model load status, running cost

## Cost Efficiency

- **Spot instances**: 60-91% discount vs on-demand ($0.016/hr vs $0.067/hr for e2-standard-2)
- **Scale to zero**: KEDA scales pods to zero during off-hours: platform used mostly 9am-6pm weekday
- **CPU inference**: Qwen2.5-coder 1.5B fits on e2-standard-2: no GPU needed ($0.45-2.48/hr for GPU instances)
- **Shared system pool**: All platform services share one node pool, not dedicated pools per service
- **Cost visibility**: Prometheus recording rules compute real-time cost/hour: data to justify spend to leadership


## GitOps & CI/CD

- **ArgoCD**: Watches Git repo, auto-syncs cluster to desired state, provides rollbacks and audit trail
- **GitHub Actions**: 
  - Builds auth-service and metrics-exporter images on every commit
  - Trivy scans: fails on CRITICAL/HIGH CVEs
  - Pushes to GCP Artifact Registry
  - Uses Workload Identity Federation for GCP auth (no service account keys in secrets)
  - Updates image tags in Helm values, commits back to trigger ArgoCD sync

## Directory Structure

```
llm-platform/
├── terraform/          # GCP infrastructure as code (VPC, GKE, DNS, Artifact Registry)
│   └── README.md       # Terraform deployment guide
├── k8s/                # Kubernetes manifests and Helm charts
│   ├── helm/           # Auth service and Ollama Helm charts
│   ├── values/         # Helm values for releases
│   ├── certs/         # cert-manager certificate resources
│   ├── docs/          # Architecture, security, troubleshooting docs
│   └── README.md      # Kubernetes deployment guide
└── services/           # Application source code
    ├── auth/           # FastAPI authentication service
    └── metrics-exporter/  # Prometheus metrics sidecar
```

## What's Implemented

- Terraform modules for VPC, GKE, node pools, Cloud DNS, Artifact Registry, IAM, bastion
- Kubernetes namespaces, Helm charts for auth-service and Ollama
- Linkerd service mesh, cert-manager with Let's Encrypt
- External Secrets Operator with GCP Secret Manager and Workload Identity
- KEDA autoscaling based on queue depth
- kube-prometheus-stack deployment

## What's Next

These features are documented but not yet implemented:

1. **Rate Limiter Service**: FastAPI + Redis sliding window, 10 req/min per key, 429 with Retry-After
2. **ArgoCD Deployment**: GitOps sync from this repo, sync waves for ordered deployment
3. **GitHub Actions Pipeline**: build, scan, push, trigger ArgoCD
4. **Grafana Dashboards**: cluster overview, inference metrics, LLM-specific with cost visibility
5. **Network Policies**: default-deny in inference namespace, explicit allow rules

## Deployment

See [terraform/README.md](./terraform/README.md) for infrastructure setup.

See [k8s/README.md](./k8s/README.md) for Kubernetes deployment.