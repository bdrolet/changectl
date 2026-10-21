terraform {
  required_version = ">= 1.5"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }

  # The bucket is not hard-coded; supply it at init:
  #   terraform init -backend-config="bucket=${PROJECT_ID}-tf-state"
  backend "gcs" {
    prefix = "changectl"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}
