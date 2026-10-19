variable "project_id" {
  description = "Dedicated GCP project id for changectl"
  type        = string
}

variable "region" {
  type    = string
  default = "us-central1"
}

variable "deployer_service_account" {
  description = "Email of the existing deployer service account (CI) that deploys the Cloud Run services"
  type        = string
}

variable "google_oauth_client_id" {
  description = "Google OAuth web client id (the client secret lives in Secret Manager)"
  type        = string
}

variable "web_hostname" {
  type    = string
  default = "changectl.drolet.ai"
}

variable "api_hostname" {
  type    = string
  default = "api.changectl.drolet.ai"
}

variable "db_tier" {
  type    = string
  default = "db-f1-micro"
}

variable "app_db_password" {
  description = "Password for the changectl_app Cloud SQL user"
  type        = string
  sensitive   = true
}

variable "owner_db_password" {
  description = "Password for the changectl (owner) Cloud SQL user, used for migrations"
  type        = string
  sensitive   = true
}

variable "web_min_instances" {
  description = "Pin to 1 for a demo to avoid cold starts"
  type        = number
  default     = 0
}

variable "api_min_instances" {
  type    = number
  default = 0
}
