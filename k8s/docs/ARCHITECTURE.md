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
│    (auth namespace)       │   │     (inference namespace)     │
│                           │   │                               │
│  - API key validation     │   │  - LLM inference              │
│  - IP allowlisting        │   │  - KEDA autoscaling           │
│  - Ollama proxy           │   │  - Metrics exporter           │
└───────────────────────────┘   │  - PVC for models             │
                                └───────────────────────────────┘
```

## Namespaces

| Namespace | Purpose |
|-----------|---------|
| `linkerd` | Linkerd control plane and viz |
| `cert-manager` | TLS certificate management |
| `keda` | Event-driven autoscaling |
| `gateway-api` | Ingress configuration |
| `monitoring` | Prometheus, Grafana, Alertmanager |
| `auth` | Authentication service |
| `inference` | Ollama LLM inference |

## Networking

- **auth-service** exposes internal service in `auth` namespace
- **ollama** exposes internal service in `inference` namespace on port 11435
- Gateway API routes traffic through Linkerd mesh
- All pod-to-pod traffic is encrypted via Linkerd mTLS

## Data Flow

1. Client request → Gateway API → Linkerd ingress
2. Linkerd routes to auth-service (authentication)
3. Authenticated requests forwarded to ollama for inference
4. Response returned through Linkerd mesh

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
