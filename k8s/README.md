# LLM Platform Kubernetes Configuration

This directory contains the Kubernetes manifests and Helm charts for deploying the LLM platform.

## Overview

The platform consists of:
- **auth-service**: Authentication service handling API key validation
- **rate-limiter**: FastAPI + Redis sliding window rate limiter (10 req/min per API key)
- **metrics-exporter**: Custom Python reverse proxy intercepting requests to expose Prometheus metrics for Ollama (tokens, latency, queue depth, cost)
- **ollama**: LLM inference server with autoscaling support
- **argocd**: GitOps continuous delivery with 14 synchronized applications

## Prerequisites

- Kubernetes cluster (v1.24+)
- kubectl configured with cluster access
- [Helm v3+](https://helm.sh/docs/intro/install/)
- [Helmfile](https://helmfile.readthedocs.io/)
- [Linkerd CLI](https://linkerd.io/) (version 2026.2.1 edge, for mesh diagnostics)

## Quick Start

ArgoCD is deployed first and manages all other deployments. The root application watches `k8s/argocd/apps/`.

```bash
# Create all required namespaces
kubectl apply -f namespaces.yaml

# Deploy ArgoCD (via helmfile or direct helm)
helmfile apply -l name=argocd

# Apply the argocd root app manifest
kubectl apply -f argocd/root-app.yaml

```

## ArgoCD Applications

The platform uses **14 ArgoCD Applications** for GitOps deployment:

| Application | Wave | Description |
|------------|------|-------------|
| cert-manager | 0 | TLS certificate management |
| external-secrets | 0 | Secrets from GCP Secret Manager |
| keda | 0 | Event-driven autoscaling |
| linkerd-crds | 0 | Linkerd CRDs |
| trust-manager | 1 | Trust anchor management |
| secrets-manifests | 1 | SecretStore and ExternalSecrets |
| gateway-api-manifests | 1 | Gateway API routes |
| linkerd-control-plane | 2 | Linkerd service mesh control plane |
| linkerd-viz | 2 | Linkerd dashboard and debugging |
| kube-prometheus | 2 | Prometheus, Grafana, Alertmanager |
| linkerd-wait | 3 | Sync hook to delay wave 4 until Linkerd webhook is ready |
| auth-service | 4 | Authentication service |
| rate-limiter | 4 | Rate limiting with Redis |
| ollama | 4 | LLM inference server |
| dashboards | 5 | Grafana dashboard configmaps |
| network-policies | 5 | Pod network policies |

    
## Directory Structure

```
k8s/
├── namespaces.yaml          # Namespace definitions
├── helmfile.yaml            # Helm releases configuration
├── argocd/                  # ArgoCD applications
│   ├── root-app.yaml        # Root application pointing to apps/
│   └── apps/                # 14 Application manifests
├── docs/                    # Documentation for components
├── platform/                # Platform components
│   ├── cert-manager/        # cert-manager certificate resources
│   ├── gateway-api/         # Gateway API resources
│   ├── network-policies/    # Network policies for pod communication
│   └── secrets/             # External secrets configuration
├── charts/                  # Helm charts
│   ├── auth-service/        # Auth service Helm chart
│   ├── rate-limiter/        # Rate limiter Helm chart (sliding window)
│   ├── ollama/              # Ollama Helm chart
│   └── metrics-exporter/    # Metrics exporter Helm chart
└── values/                  # Helm values for releases
```

## Deployment Order

ArgoCD uses **sync waves** for ordered deployment:

1. **Wave 0**: cert-manager, external-secrets, keda, linkerd-crds
2. **Wave 1**: trust-manager, secrets-manifests, gateway-api-manifests
3. **Wave 2**: linkerd-control-plane, linkerd-viz, kube-prometheus
4. **Wave 3 (Linkerd Wait Mechanism)**: A critical `linkerd-wait` Job executes a 30-second sleep. ArgoCD considers the Linkerd control plane (Wave 2) healthy immediately, but the Mutating Webhook takes slightly longer to register with the Kubernetes API server. This wait guarantees the webhook is fully operational so it does not silently drop sidecar injection for the subsequent application workloads.
5. **Wave 4**: Application workloads safely deploy (`auth-service`, `rate-limiter`, `ollama`) and successfully receive Linkerd sidecar injections.
6. **Wave 5**: dashboards, network-policies

## Monitoring

Prometheus is available in the `monitoring` namespace. Access via:
```bash
kubectl port-forward -n monitoring svc/kube-prometheus-kube-prome-prometheus 9090
```

Grafana (built into kube-prometheus-stack):
```bash
kubectl port-forward -n monitoring svc/kube-prometheus-grafana 3000
```

## Grafana Dashboards

This project includes several Grafana dashboards, which are declaratively managed and deployed as ConfigMaps.

| Dashboard | Description |
| :--- | :--- |
| **Cluster Overview** | Custom dashboard showing node CPU, memory, and pod health across the platform. |
| **Inference Metrics** | Custom dashboard monitoring key inference performance indicators such as request rate, latency (p50/p95/p99), error rate, and queue depth. |
| **LLM-Specific Metrics** | Custom dashboard providing insights into LLM-specific data, including tokens per second, prompt eval duration, generation duration, model load status, and estimated cost per hour (derived from Prometheus recording rules multiplied against GCP instance pricing). |
| **Kubernetes / Views / Global*** | A comprehensive overview of the entire Kubernetes cluster, including global CPU and RAM usage, and a Kubernetes resource count. |
| **Kubernetes / Views / Nodes*** | Detailed metrics for each node in the cluster, covering CPU, memory, and disk usage, as well as pod information and network statistics. |
| **Kubernetes / Views / Namespaces*** | A breakdown of resource usage by namespace, including CPU and RAM usage, pod statuses, and storage details. |

All the **Kubernetes / Views/\*** dashboards are from the [grafana-dashboards-kubernetes](https://github.com/dotdc/grafana-dashboards-kubernetes/tree/master) repository and are subject to its license.*

## Troubleshooting

See [TROUBLESHOOTING.md](./docs/TROUBLESHOOTING.md) for common issues.
