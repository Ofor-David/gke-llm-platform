# Namespaces

This document describes the namespaces used in the LLM Platform.

## Namespace List

| Namespace | Purpose | Labels/Annotations |
|-----------|---------|---------------------|
| `linkerd` | Linkerd service mesh control plane | `linkerd.io/is-control-plane: "true"` |
| `cert-manager` | cert-manager for TLS certificates | - |
| `keda` | Event-driven autoscaling | - |
| `gateway-api` | Gateway API CRDs and routes | - |
| `monitoring` | Prometheus, Grafana, Alertmanager | - |
| `inference` | Ollama LLM inference service | `linkerd.io/inject: enabled` |
| `auth` | Authentication service | `linkerd.io/inject: enabled` |

## Namespace Creation

All namespaces are defined in `namespaces.yaml` and can be applied with:

```bash
kubectl apply -f namespaces.yaml
```

## Linkerd Injection

The `inference` and `auth` namespaces have Linkerd sidecar injection enabled via the annotation:
```yaml
metadata:
  annotations:
    linkerd.io/inject: enabled
```

All pods deployed to these namespaces will automatically have the Linkerd proxy sidecar injected.

## Resource Quotas

To add resource quotas to a namespace:

```yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: default
  namespace: <namespace>
spec:
  hard:
    requests.cpu: "4"
    requests.memory: 8Gi
    limits.cpu: "8"
    limits.memory: 16Gi
    pods: "10"
```
