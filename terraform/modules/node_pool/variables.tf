variable "region"{
    type = string
}
variable "gke_cluster_name" {
  type = string
}
variable "node_sa_email" {
  type = string
}

variable "system_node_type"{
    type = string
}
variable "system_node_disk_size"{
    type = number
}
variable "system_node_disk_type" {
  type = string
}
variable "max_system_node_count" {
  type = number
  default = 1
}

variable "inference_node_type"{
    type = string
}
variable "inference_node_disk_size"{
    type = number
}
variable "inference_node_disk_type" {
  type = string
}
variable "max_inference_node_count" {
  type = number
  default = 2
}