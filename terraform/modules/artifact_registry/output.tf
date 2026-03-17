output "workload_identity_pool_name" {
  value = google_iam_workload_identity_pool.wip.name
}
output "wi_provider_name" {
  value = google_iam_workload_identity_pool_provider.github.name
}