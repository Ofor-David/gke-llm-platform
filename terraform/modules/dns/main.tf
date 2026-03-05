# terraform/modules/dns/main.tf
resource "google_dns_managed_zone" "primary" {
  name        = "llm-platform-zone"
  dns_name    = "${var.dns_name}."
  description = "LLM Platform DNS zone"
  visibility  = "public"
  project     = var.project_id
}

resource "google_dns_record_set" "subdomains" {
  for_each = toset(["api", "argocd", "grafana"])

  name         = "${each.value}.${var.dns_name}."
  type         = "A"
  ttl          = 300
  managed_zone = google_dns_managed_zone.primary.name
  rrdatas      = [var.gateway_ip]
  project      = var.project_id
}