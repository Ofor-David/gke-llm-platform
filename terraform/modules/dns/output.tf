# terraform/modules/dns/outputs.tf
output "name_servers" {
  value = google_dns_managed_zone.primary.name_servers
}