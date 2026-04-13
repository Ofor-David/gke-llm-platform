# Security

## TLS Certificates

Certificates are managed by cert-manager in the `cert-manager` namespace.

### Certificate Types

- **Linkerd Identity**: Used for mTLS between services
- **Trust Anchor**: Root CA for Linkerd
- **LLM Platform**: Application-specific certificates. TLS termination at the Gateway uses Let's Encrypt certificates issued and auto-renewed by cert-manager via DNS-01 challenge against GCP Cloud DNS for the `xikhub.store` domain.

### Certificate Rotation

Linkerd certificates can be rotated automatically or manually. For automatic rotation with cert-manager, see the [official Linkerd documentation](https://linkerd.io/2-edge/tasks/automatically-rotating-control-plane-tls-credentials/).

#### Manual Certificate Rotation

To manually rotate Linkerd certificates:

1. Check current certificate status:
```bash
kubectl get certificates -n linkerd
kubectl get issuers -n linkerd
```

2. For trust anchor rotation, refer to [Linkerd Trust Anchor Rotation](https://linkerd.io/2-edge/tasks/rotating_control_plane_tls_credentials/)

#### Check Certificate Status

```bash
kubectl get certificates -A
kubectl get issuers -A
```

## Secrets Management

### External Secrets

Secrets are managed via External Secrets Operator (ESO) in `cert-manager` namespace. ESO is configured to authenticate to GCP Secret Manager using Workload Identity.

**Important Note on ESO Setup:** 
Before the External Secrets Operator can sync secrets from GCP Secret Manager, the initial Kubernetes Secret containing the mapping to the GCP Service Account (if required by your specific ESO configuration) **must be created manually** using the `gcloud` CLI or the GCP console.

Configuration files in `platform/secrets/`:
- `secret-store.yaml`: SecretStore provider configuration
- `external-secrets.yaml`: ExternalSecret resources

# Create Required gcloud secrets
```
echo -n '{"api-key": "api-key-value"}' | gcloud secrets create ollama-api-key \
    --data-file=- \
    --project=<project-id>
```
```
echo -n '{"userKey": "user", "passwordKey": "password"}' | gcloud secrets create grafana-admin-password \
    --data-file=- \   
    --project=<project-id>
```

### Application Secrets

| Secret | Namespace | Purpose |
|--------|-----------|---------|
| `ollama-api-key` | inference | Ollama API key |

## Linkerd mTLS

All service-to-service traffic is encrypted via Linkerd.

### Verify mTLS

```bash
linkerd check --proxy
```

## Rate Limiting

### Sliding Window Rate Limiter

The platform implements a **sliding window** rate limiter using Redis to prevent cost abuse and protect against runaway scripts or compromised API keys.

| Property | Value |
|----------|-------|
| Limit | 10 requests/minute per API key |
| Algorithm | Sliding window |
| Storage | Redis |
| Namespace | `ratelimit` |

### Why Sliding Window?

The sliding window algorithm provides superior protection compared to fixed-window approaches:

- **Prevents burst abuse**: Unlike fixed windows that reset every minute, sliding windows track request timing continuously—preventing clients from sending 10 requests at :59 and another 10 at :00
- **Fair resource allocation**: Each API key has isolated limits, so one misbehaving client cannot exhaust resources for others
- **Cost control**: At 10 req/min, even a stolen API key is limited to ~6,000 requests/hour, minimizing potential charges

### Rate Limiter Response

When a client exceeds the limit, the rate limiter returns:
- **HTTP 429** (Too Many Requests)
- `Retry-After` header indicating seconds to wait

This allows clients to implement automatic backoff without manual intervention.

## CI/CD Pipeline Security

- GitHub Actions builds container images and pushes them to GCP Artifact Registry.
- Authentication from GitHub Actions to GCP is handled securely via **Workload Identity Federation**. No static service account keys are stored in GitHub secrets.

## GATEWAY API

Gateway API resources in `gateway_api/` define ingress rules:
- `routes.yaml`: HTTP route definitions
- `backend-policy.yaml`: Backend service policies
- `healthcheck-policy.yaml`: Health check configuration
- `reference-grants.yaml`: Cross-namespace permissions

## Pod Security

- Pods run with Linkerd sidecar injection enabled
- Resource limits configured for all workloads
- Non-root container execution recommended

## Image Security

- Use specific image tags (not `latest`)
- Images stored in GCP Artifact Registry
- Pull policy: `IfNotPresent`

## ArgoCD Security

ArgoCD is deployed in the `argocd` namespace for GitOps-based deployments.

### Accessing ArgoCD UI

```bash
kubectl port-forward -n argocd svc/argocd-server 8080:443
```

Default username: `admin`. Password can be retrieved via:
```bash
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d
```

### ArgoCD Security Best Practices

- Change default admin password after first login
- Use SSO integration for production deployments
- Enable RBAC policies
- Review [ArgoCD security documentation](https://argo-cd.readthedocs.io/en/stable/operator-manual/security/)
