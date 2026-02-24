output "nat_ip" {
  value = google_compute_instance.bastion.network_interface[0].network_ip
}

output "iap_gateway_url" {
  description = "IAP Gateway URL for accessing GKE control plane"
  value       = "https://${var.project_id}.cloud.goog:8888"
}