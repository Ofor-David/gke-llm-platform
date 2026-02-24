output "gke_cluster_name" {
  value = google_container_cluster.llm_cluster.name
}

output "private_gke_endpoint" {
  value = google_container_cluster.llm_cluster.private_cluster_config[0].private_endpoint
}