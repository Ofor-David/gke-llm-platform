output "gateway_static_ip" {
  value = module.networking.gateway_static_ip
}
output "primary_nameservers" {
  value = module.dns.name_servers
}
output "ds_record" {
  description = "Add this to your registrar's DNSSEC settings"
  value = module.dns.ds_record
}
output "wi_provider_name" {
  description = "Name of the workload identity pool provider for github Actions"
  value = module.artifact_registry.wi_provider_name
}