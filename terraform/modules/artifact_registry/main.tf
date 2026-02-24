resource "google_iam_workload_identity_pool" "wip" {
  workload_identity_pool_id = "github-pool"
  lifecycle {
    prevent_destroy = true
  }
}

resource "google_artifact_registry_repository" "repo" {
  location      = var.region
  repository_id = "container-images"
  format        = "DOCKER"
  
  docker_config {
    immutable_tags = false
  }

  lifecycle {
    prevent_destroy = true
  }
}
# Create the Workload Identity Pool Provider for GitHub
resource "google_iam_workload_identity_pool_provider" "github" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.wip.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-actions"
  display_name                       = "github-actions"
  description                        = "GitHub Actions identity pool provider"
  disabled                           = false

  attribute_condition = <<EOT
    assertion.repository_owner_id == "${var.repo_owner_id}" &&
    attribute.repository == "${var.github_repo}" &&
    assertion.ref == "refs/heads/${var.github_branch}" &&
    assertion.ref_type == "branch"
  EOT

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.actor"      = "assertion.actor"
    "attribute.aud"        = "assertion.aud"
    "attribute.repository" = "assertion.repository"
  }
  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
  lifecycle {
    prevent_destroy = true
  }
}

