output "gke_vpc" {
  value = google_compute_network.vpc.id
}

output "gke_subnet" {
  value = google_compute_subnetwork.gke_subnet.id
}

output "bastion_subnet_cidr" {
  value = google_compute_subnetwork.bastion_subnet.ip_cidr_range
}
output "bastion_subnet" {
  value = google_compute_subnetwork.bastion_subnet.id
}
