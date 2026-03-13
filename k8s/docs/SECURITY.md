# Security

## TLS Certificates

Certificates are managed by cert-manager in the `cert-manager` namespace.

### Certificate Types

- **Linkerd Identity**: Used for mTLS between services
- **Trust Anchor**: Root CA for Linkerd
- **LLM Platform**: Application-specific certificates

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

Secrets are managed via External Secrets Operator in `cert-manager` namespace.

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
