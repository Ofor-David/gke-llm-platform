## Namespaces

| Namespace | Purpose |
|-----------|---------|
| `linkerd` | Linkerd control plane and viz |
| `cert-manager` | TLS certificate management |
| `keda` | Event-driven autoscaling |
| `gateway-api` | Ingress configuration |
| `monitoring` | Prometheus, Grafana, Alertmanager |
| `argocd` | GitOps continuous delivery (17 applications) |
| `auth` | Authentication service |
| `ratelimit` | Rate limiter (sliding window Redis) |
| `inference` | Ollama LLM inference |

## ArgoCD Applications

The platform uses **17 ArgoCD Applications** for GitOps deployment with sync waves:

| Wave | Application | Chart/Path |
|------|-------------|------------|
| 0 | cert-manager | cert-manager/cert-manager v1.19.2 |
| 0 | external-secrets | external-secrets v2.0.0 |
| 0 | keda | kedacore/keda v2.19.0 |
| 0 | linkerd-crds | linkerd-edge/linkerd-crds 2026.2.1 |
| 1 | trust-manager | cert-manager/trust-manager v0.21.1 |
| 1 | cert-manifests | k8s/platform/cert-manager |
| 1 | secrets-manifests | k8s/platform/secrets |
| 1 | gateway-api-manifests | k8s/platform/gateway-api |
| 2 | linkerd-control-plane | linkerd-edge 2026.2.1 |
| 2 | linkerd-viz | linkerd-edge 2026.2.1 |
| 2 | kube-prometheus | prometheus-community v82.1.0 |
| 3 | linkerd-wait | argocd Job |
| 4 | auth-service | k8s/charts/auth-service |
| 4 | rate-limiter | k8s/charts/rate-limiter |
| 4 | ollama | k8s/charts/ollama |
| 5 | dashboards | k8s/dashboards/configmaps |
| 5 | network-policies | k8s/platform/network-policies |

## Networking

- **auth-service** exposes internal service in `auth` namespace
- **ollama** exposes internal service in `inference` namespace on port 11435
- Gateway API routes traffic through Linkerd mesh
- All pod-to-pod traffic is encrypted via Linkerd mTLS

## Data Flow

1. Client request → Gateway API → Linkerd ingress
2. Linkerd routes to auth-service (authentication)
3. Authenticated requests forwarded to rate-limiter (sliding window check)
4. If within limit, request proceeds to the metrics-exporter proxy
5. Metrics-exporter intercepts request, extracts inference metrics, and forwards to Ollama
6. Response returned through Linkerd mesh

## Network Policies

Network policies in `platform/network-policies/` control pod-to-pod communication:
- `inference-network-policy.yaml`: Controls traffic to ollama
- `auth-network-policy.yaml`: Controls traffic to auth-service
- `ratelimit-network-policy.yaml`: Controls traffic to rate-limiter

## Why Sliding Window Rate Limiting?

The rate limiter uses a **sliding window** algorithm with Redis, which offers significant advantages over fixed window approaches:

- **Smooth rate distribution**: Requests are spread evenly across the time window, preventing the "burst at window boundaries" problem where fixed windows allow double the rate at midnight
- **Per-API-key isolation**: Each client gets their own rate limit bucket, preventing one abusive client from affecting others
- **Cost protection**: With 10 req/min per key, a compromised API key can only generate ~600 requests/hour—limiting potential abuse
- **Simple yet effective**: Sliding window provides good accuracy without the complexity of token bucket or leaky bucket algorithms

This is a smart architectural choice because it protects the platform from runaway scripts, accidental DDoS from misconfigured clients, and credential abuse—while being lightweight enough to run on minimal infrastructure.

## Storage

- Ollama uses PersistentVolumeClaim for model storage
- Default storage: 50Gi (configured in PVC)

## Security

- **mTLS**: All service-to-service communication encrypted via Linkerd
- **Certificates**: Managed by cert-manager with automatic renewal
- **Secrets**: External Secrets Operator for secret management
- **Identity**: Linkerd identity with Kubernetes CA

## Autoscaling

- KEDA scales Ollama replicas based on the custom Prometheus metric `ollama_queue_depth` (exposed by the metrics exporter sidecar).
- **Scale Up Threshold**: When queue depth exceeds 3 concurrent requests, KEDA adds a second Ollama pod.
- **Scale Down**: Scales back down when queue depth falls below the threshold for 5 minutes.
- **Minimum Replicas**: The minimum replica count is maintained at 1 (warm node/pod). It does not scale to zero in order to avoid a 5-6 minute cold start delay.
