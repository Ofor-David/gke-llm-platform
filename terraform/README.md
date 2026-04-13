# LLM Platform Terraform

Terraform configuration for deploying an LLM platform infrastructure on Google Cloud.

## Overview

This Terraform project provisions a complete GKE-based infrastructure for hosting LLM workloads, including:

- Google Kubernetes Engine (GKE) cluster
- VPC networking with subnets for GKE and bastion host
- Cloud DNS with DNSSEC
- Artifact Registry for container images
- IAM roles and workload identity
- Bastion host for private cluster access

## Prerequisites

- Google Cloud SDK (`gcloud`) installed and configured
- Terraform >= 1.6.0
- Valid GCP project with billing enabled
- GCS Bucket for Terraform remote state (specified in `provider.tf`)

## Usage

### 1. Initialize Terraform

```bash
terraform init
```

### 2. Create a `terraform.tfvars` file

Create a `terraform.tfvars` file with your configuration:

```hcl
project_id             = "your-gcp-project-id"
region                 = "your-region"
cluster_name           = "llm-platform"

# Node pools
system_node_type       = "e2-standard-4"
system_node_disk_size  = 100
system_node_disk_type  = "pd-ssd"
max_system_node_count  = 1

# Inference pool deliberately uses Spot instances for significant cost savings (60-91%).
# Minimum node count is maintained at 1 to ensure a warm node and avoid a 5-6 minute cold start.
inference_node_type    = "n2-standard-8"
inference_node_disk_size = 500
inference_node_disk_type = "pd-ssd"
max_inference_node_count = 2

# IAP Access
iap_allowed_users = [
  "user:admin@example.com",
  "group:platform-team@example.com"
]

# GitHub Integration
github_branch = "main"
github_repo   = "your-username/your-repo"
repo_owner_id = "your-github-org-id"

# DNS
dns_name = "xikhub.store"
```

### 3. Plan and Apply

```bash
terraform plan -out=tfplan
terraform apply tfplan
```

## Variables

| Variable | Description | Type | Default |
|----------|-------------|------|---------|
| `project_id` | GCP project ID | `string` | required |
| `region` | GCP region | `string` | required |
| `cluster_name` | GKE cluster name | `string` | required |
| `system_node_type` | System node machine type | `string` | required |
| `system_node_disk_size` | System node disk size (GB) | `number` | required |
| `system_node_disk_type` | System node disk type | `string` | required |
| `max_system_node_count` | Maximum system nodes | `number` | 1 |
| `inference_node_type` | Inference node machine type | `string` | required |
| `inference_node_disk_size` | Inference node disk size (GB) | `number` | required |
| `inference_node_disk_type` | Inference node disk type | `string` | required |
| `max_inference_node_count` | Maximum inference nodes | `number` | required |
| `iap_allowed_users` | Users/groups allowed via IAP | `list(string)` | `[]` |
| `github_branch` | GitHub branch for CI/CD | `string` | required |
| `github_repo` | GitHub repository | `string` | required |
| `repo_owner_id` | GitHub owner/org ID | `string` | required |
| `secrets_namespace` | External secrets namespace | `string` | `"external-secrets"` |
| `secrets_ksa_name` | Kubernetes service account for secrets | `string` | `"secrets-ksa"` |
| `dns_name` | DNS zone name | `string` | required |

## Outputs

| Output | Description |
|--------|-------------|
| `gateway_static_ip` | Static IP for Cloud NAT gateway |
| `primary_nameservers` | DNS name servers (add to registrar) |
| `ds_record` | DNSSEC DS record (add to registrar) |

## Modules

| Module | Description |
|--------|-------------|
| `enable_apis` | Enables required GCP APIs |
| `iam` | Configures IAM roles and workload identity |
| `dns` | Creates Cloud DNS zone |
| `networking` | Creates VPC, subnets, and NAT |
| `gke` | Creates private GKE cluster |
| `bastion` | Creates bastion host for cluster access |
| `node_pool` | Creates system and inference node pools |
| `artifact_registry` | Creates Artifact Registry repository |

## Bastion Access

The GKE cluster uses a private endpoint only. Access is provided through a bastion host with IAP tunneling.

### Using the connect script

```bash
./connect-gke.sh
```

This script:
1. Starts an IAP tunnel to the bastion on port 8888
2. Updates kubeconfig to use `localhost:8888` as the API server
3. Displays connection status

To stop the tunnel, press Ctrl+C or run `kill` on the tunnel process.

### Manual setup

If you need to configure manually:

```bash
# Start IAP tunnel
gcloud compute start-iap-tunnel bastion-host 8888 \
  --project=$PROJECT_ID \
  --zone=$REGION-a \
  --local-host-port=localhost:8888

# Update kubeconfig (in another terminal)
kubectl config set-cluster gke_${PROJECT}_${ZONE}_${CLUSTER} \
  --server=https://localhost:8888 \
  --insecure-skip-tls-verify=true
```

The bastion runs a `socat` service that forwards traffic to the GKE private control plane endpoint.

## Cleanup

To destroy all resources:

```bash
terraform destroy
```

## License

MIT
