# LLM Platform Kubernetes Configuration

This directory contains the Kubernetes manifests and Helm charts for deploying the LLM platform.

## Overview

The platform consists of:
- **auth-service**: Authentication service handling API key validation
- **rate-limiter**: FastAPI + Redis sliding window rate limiter (10 req/min per API key)
- **ollama**: LLM inference server with autoscaling support

## Prerequisites

- Kubernetes cluster (v1.24+)
- kubectl configured with cluster access
- [Helm v3+](https://helm.sh/docs/intro/install/)
- [Helmfile](https://helmfile.readthedocs.io/)
- [Kustomize](https://kubectl.docs.kubernetes.io/guides/introduction/kustomize/)
- [Linkerd CLI](https://linkerd.io/2.16/getting-started/) (for mesh diagnostics)

## Quick Start

```bash
# Apply namespaces first
kubectl apply -f namespaces.yaml

# Deploy all pre releases via helmfile
helmfile apply -l order=pre

# Deploy non helm manifests
kubectl apply -k certs 
```
Run `kubectl get certificates -A` to verify proper installation. Should return a response like this:
```
NAMESPACE      NAME                      READY   SECRET                    AGE
cert-manager   linkerd-trust-anchor      True    linkerd-trust-anchor      20s
cert-manager   trust-manager             True    trust-manager-tls         20s
gateway-api    llm-platform-tls          True    gateway-tls               20s
linkerd        linkerd-identity-issuer   True    linkerd-identity-issuer   20s
```
Duplicate linkerd trust anchor. Needed for certificate rotation later on.

```
kubectl get secret -n cert-manager linkerd-trust-anchor -o yaml \
        | sed -e s/linkerd-trust-anchor/linkerd-previous-anchor/ \
        | egrep -v '^  *(resourceVersion|uid)' \
        | kubectl apply -f - 
```

Deploy external secrets, gateway api for ingress, and remaining helm releases.

```
kubectl apply -f secrets -f gateway_api

helmfile apply -l order=post
```

## Directory Structure

```
k8s/
├── namespaces.yaml          # Namespace definitions
├── helmfile.yaml            # Helm releases configuration
├── docs/                    # Documentation for components
├── platform/                # Platform components
│   ├── cert-manager/        # cert-manager certificate resources
│   ├── gateway-api/         # Gateway API resources
│   └── secrets/             # External secrets configuration
├── charts/                  # Helm charts
│   ├── auth-service/        # Auth service Helm chart
│   ├── rate-limiter/        # Rate limiter Helm chart (sliding window)
│   └── ollama/              # Ollama Helm chart
└── values/                  # Helm values for releases
```

## Deployment Order

1. **Pre-install**: cert-manager, trust-manager, external-secrets, keda
2. **Post-install**: linkerd-control-plane, linkerd-viz, kube-prometheus, auth-service, ollama

## Monitoring

Prometheus is available in the `monitoring` namespace. Access via:
```bash
kubectl port-forward -n monitoring svc/kube-prometheus-kube-prome-prometheus 9090
```

## Troubleshooting

See [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) for common issues.
