provider "google" {
  project = var.project_id
  region  = var.region
}

terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "7.26.0"
    }
  }
  backend "gcs" {
    bucket = "llm-platform-state-bucket"
    prefix = "tf-state"
  }
}
