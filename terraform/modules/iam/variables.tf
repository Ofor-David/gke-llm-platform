variable "project_id" {
  type = string
}

variable "iap_allowed_users" {
  type        = list(string)
  description = "List of users/groups allowed to access via IAP tunnel"
}

variable "workload_identity_pool_name" {
  type =  string
}

variable "github_repo" {
  type = string
}

variable "secrets_namespace" {
  type = string
}

variable "secrets_ksa_name" {
  type = string
}