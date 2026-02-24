resource "google_container_cluster" "llm_cluster" {
  name       = var.cluster_name
  location   = "${var.region}-a"
  network    = var.gke_vpc
  subnetwork = var.gke_subnet

  initial_node_count       = 1
  remove_default_node_pool = true

  release_channel {
    channel = "REGULAR"
  }
  networking_mode = "VPC_NATIVE"

  ip_allocation_policy {
    cluster_secondary_range_name  = "pods-range"
    services_secondary_range_name = "services-range"
  }

  private_cluster_config {
    enable_private_endpoint = true
    enable_private_nodes    = true
    master_ipv4_cidr_block  = "10.50.0.0/28"
  }

  master_authorized_networks_config {
    cidr_blocks {
      cidr_block   = var.bastion_subnet_cidr
      display_name = "bastion-host"
    }
  }
 # Enable GKE Dataplane V2 (replaces kube-proxy)
  datapath_provider = "ADVANCED_DATAPATH" # Corresponds to GKE Dataplane, adds cilium
  enable_shielded_nodes = true

  deletion_protection = false

  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }

}

