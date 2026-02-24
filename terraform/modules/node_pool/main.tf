resource "google_container_node_pool" "system-pool" {
  name     = "system-pool"
  location = "${var.region}-a"
  cluster  = var.gke_cluster_name

  node_config {
    spot  = false
    machine_type = var.system_node_type
    disk_size_gb = var.system_node_disk_size
    disk_type    = var.system_node_disk_type

    # Google recommends custom service accounts that have cloud-platform scope and permissions granted via IAM Roles.
    service_account = var.node_sa_email
    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform"
    ]
    workload_metadata_config {
      mode = "GKE_METADATA" # This enables the Metadata Server
    }
    labels = { pool = "system" }
  }
  autoscaling {
    min_node_count = 1
    max_node_count = var.max_system_node_count
  }
}
resource "google_container_node_pool" "inference-pool" {
  name     = "inference-pool"
  location = "${var.region}-a"
  cluster  = var.gke_cluster_name

  node_config {
    spot  = true
    machine_type = var.inference_node_type
    disk_size_gb = var.inference_node_disk_size
    disk_type    = var.inference_node_disk_type

    # Google recommends custom service accounts that have cloud-platform scope and permissions granted via IAM Roles.
    service_account = var.node_sa_email
    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform"
    ]
    workload_metadata_config {
      mode = "GKE_METADATA" # This enables the Metadata Server
    }
    taint {
      key    = "pool"
      value  = "inference"
      effect = "NO_SCHEDULE"
    }
    labels = { pool = "inference" }
  }
  autoscaling {
    min_node_count = 1
    max_node_count = var.max_inference_node_count
  }
}
