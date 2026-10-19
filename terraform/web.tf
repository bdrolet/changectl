locals {
  web_image = "${var.region}-docker.pkg.dev/${var.project_id}/changectl/changectl-web:latest"
}

resource "google_cloud_run_v2_service" "web" {
  name     = "changectl-web"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.web.email
    timeout         = "60s"

    scaling {
      min_instance_count = var.web_min_instances
      max_instance_count = 2
    }

    containers {
      image = local.web_image

      ports {
        container_port = 8080
      }

      env {
        name  = "API_URL"
        value = "https://${var.api_hostname}"
      }
      env {
        name  = "AUTH_URL"
        value = "https://${var.web_hostname}"
      }
      env {
        name  = "AUTH_TRUST_HOST"
        value = "true"
      }
      env {
        name  = "AUTH_GOOGLE_ID"
        value = var.google_oauth_client_id
      }
      env {
        name = "AUTH_SECRET"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.this["changectl-auth-secret"].secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "AUTH_GOOGLE_SECRET"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.this["changectl-google-oauth-client"].secret_id
            version = "latest"
          }
        }
      }
    }
  }

  lifecycle {
    ignore_changes = [template[0].containers[0].image]
  }

  depends_on = [
    google_artifact_registry_repository.changectl,
    google_secret_manager_secret_iam_member.web_secrets,
  ]
}

resource "google_cloud_run_v2_service_iam_member" "web_public" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.web.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
