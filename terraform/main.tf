module "enable_apis" {
  source     = "./modules/enable_apis"
  project_id = var.project_id
}
module "iam" {
  depends_on                  = [module.enable_apis.prep]
  source                      = "./modules/iam"
  project_id                  = var.project_id
  iap_allowed_users           = var.iap_allowed_users
  workload_identity_pool_name = module.artifact_registry.workload_identity_pool_name
  github_repo                 = var.github_repo
  secrets_ksa_name            = var.secrets_ksa_name
  secrets_namespace           = var.secrets_namespace
}
module "networking" {
  source     = "./modules/networking"
  depends_on = [module.enable_apis.prep]

  region = var.region
}
module "gke" {
  depends_on          = [module.enable_apis.prep]
  project_id          = var.project_id
  source              = "./modules/gke"
  region              = var.region
  cluster_name        = var.cluster_name
  gke_subnet          = module.networking.gke_subnet
  gke_vpc             = module.networking.gke_vpc
  bastion_subnet_cidr = module.networking.bastion_subnet_cidr
}
module "bastion" {
  source     = "./modules/bastion"
  depends_on = [module.enable_apis.prep]

  project_id           = var.project_id
  region               = var.region
  bastion_subnet       = module.networking.bastion_subnet
  private_gke_endpoint = module.gke.private_gke_endpoint
}
module "node_pool" {
  depends_on       = [module.enable_apis.prep]
  source           = "./modules/node_pool"
  region           = var.region
  gke_cluster_name = module.gke.gke_cluster_name
  node_sa_email    = module.iam.node_sa_email

  max_system_node_count = var.max_system_node_count
  system_node_type      = var.system_node_type
  system_node_disk_size = var.system_node_disk_size
  system_node_disk_type = var.system_node_disk_type

  max_inference_node_count = var.max_inference_node_count
  inference_node_type      = var.inference_node_type
  inference_node_disk_size = var.inference_node_disk_size
  inference_node_disk_type = var.inference_node_disk_type
}
module "artifact_registry" {
  source     = "./modules/artifact_registry"
  depends_on = [module.enable_apis.prep]

  region        = var.region
  github_branch = var.github_branch
  github_repo   = var.github_repo
  repo_owner_id = var.repo_owner_id
}
