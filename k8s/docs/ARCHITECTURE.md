# Architecture

## Components

```
┌─────────────────────────────────────────────────────────────────┐
│                        Gateway API                              │
│                     (gateway-api namespace)                     │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                       Linkerd Service Mesh                      │
│                     (linkerd namespace - mTLS)                  │
└─────────────────────────────────────────────────────────────────┘
                                │
                ┌───────────────┴───────────────┐
                ▼                               ▼
┌───────────────────────────┐   ┌───────────────────────────────┐
│      auth-service         │   │         ollama                │
│    (auth namespace)       │   │     (inference namespace)    │
│                           │   │                               │
│  - API key validation     │   │  - LLM inference              │
│  - IP allowlisting        │   │  - KEDA autoscaling           │
│  - Ollama proxy           │   │  - Metrics exporter           │
└───────────────────────────┘   │  - PVC for models             │
                │               └───────────────────────────────┘
                ▼
┌───────────────────────────┐
│      rate-limiter          │
│    (ratelimit namespace)   │
│                           │
│  - Sliding window Redis    │
│  - 10 req/min per key     │
│  - Returns 429 + Retry-   │
│    After on limit         │
└───────────────────────────┘

┌───────────────────────────┐
│        ArgoCD             │
│    (argocd namespace)     │
│                           │
│  - GitOps deployment      │
│  - Application sync       │
│  - UI dashboard           │
└───────────────────────────┘
```

## Namespaces

| Namespace | Purpose |
|-----------|---------|
| `linkerd` | Linkerd control plane and viz |
| `cert-manager` | TLS certificate management |
| `keda` | Event-driven autoscaling |
| `gateway-api` | Ingress configuration |
| `monitoring` | Prometheus, Grafana, Alertmanager |
| `argocd` | GitOps continuous delivery |
| `auth` | Authentication service |
| `ratelimit` | Rate limiter (sliding window Redis) |
| `inference` | Ollama LLM inference |

## Networking

- **auth-service** exposes internal service in `auth` namespace
- **ollama** exposes internal service in `inference` namespace on port 11435
- Gateway API routes traffic through Linkerd mesh
- All pod-to-pod traffic is encrypted via Linkerd mTLS

## Data Flow

1. Client request → Gateway API → Linkerd ingress
2. Linkerd routes to auth-service (authentication)
3. Authenticated requests forwarded to rate-limiter (sliding window check)
4. If within limit, request proceeds to ollama for inference
5. Response returned through Linkerd mesh

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

- KEDA scales ollama replicas based on Prometheus metrics
