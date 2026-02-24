variable "project_id" {
  type = string
}
variable "region" {
  type = string
}
variable "cluster_name" {
  type = string
}

//// Node pool config
variable "system_node_type" {
  type = string
}
variable "system_node_disk_size" {
  type = number
}
variable "system_node_disk_type" {
  type = string
}
variable "max_system_node_count" {
  type    = number
  default = 1
}

variable "inference_node_type" {
  type = string
}
variable "inference_node_disk_size" {
  type = number
}
variable "inference_node_disk_type" {
  type = string
}
variable "max_inference_node_count" {
  type = number
}

//// IAP
variable "iap_allowed_users" {
  type        = list(string)
  description = "Users/groups allowed to access via IAP (e.g., 'user:admin@example.com')"
  default     = []
}

//// Artifact Registry
variable "github_branch" {
  type = string
}
variable "github_repo" {
  type = string
}
variable "repo_owner_id" {
  type = string
}
