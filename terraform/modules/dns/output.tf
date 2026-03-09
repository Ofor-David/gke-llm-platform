# terraform/modules/dns/outputs.tf
output "name_servers" {
  value = google_dns_managed_zone.primary.name_servers
}
data "google_dns_keys" "zone_keys" {
  managed_zone = google_dns_managed_zone.primary.id
}

output "ds_record" {
  description = "Add this to your registrar's DNSSEC settings"
  value = {
    key_tag     = data.google_dns_keys.zone_keys.key_signing_keys[0].key_tag
    algorithm   = data.google_dns_keys.zone_keys.key_signing_keys[0].algorithm
    digest_type = data.google_dns_keys.zone_keys.key_signing_keys[0].digests[0].type
    digest      = data.google_dns_keys.zone_keys.key_signing_keys[0].digests[0].digest
  }
}
