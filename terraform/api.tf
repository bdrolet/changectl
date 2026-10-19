resource "google_artifact_registry_repository" "changectl" {
  repository_id = "changectl"
  format        = "DOCKER"
  location      = var.region

  cleanup_policy_dry_run = false

  cleanup_policies {
    id     = "delete-untagged-after-7d"
    action = "DELETE"
    condition {
      tag_state  = "UNTAGGED"
      older_than = "604800s"
    }
  }

  cleanup_policies {
    id     = "keep-3-most-recent"
    action = "KEEP"
    most_recent_versions {
      keep_count = 3
    }
  }
}

locals {
  api_image = "${var.region}-docker.pkg.dev/${var.project_id}/changectl/changectl-api:latest"
}

resource "google_cloud_run_v2_service" "api" {
  name     = "changectl-api"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.api.email
    timeout         = "60s"

    scaling {
      min_instance_count = var.api_min_instances
      max_instance_count = 2
    }

    volumes {
      name = "cloudsql"
      cloud_sql_instance {
        instances = [google_sql_database_instance.changectl.connection_name]
      }
    }

    containers {
      # Placeholder until the first image push; CI updates it afterwards.
      image = local.api_image

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          memory = "512Mi"
        }
      }

      volume_mounts {
        name       = "cloudsql"
        mount_path = "/cloudsql"
      }

      env {
        name  = "CLOUD_SQL_CONNECTION_NAME"
        value = google_sql_database_instance.changectl.connection_name
      }
      env {
        name  = "POSTGRES_DB"
        value = google_sql_database.changectl.name
      }
      env {
        name  = "POSTGRES_USER"
        value = google_sql_user.app.name
      }
      env {
        name = "POSTGRES_PASSWORD"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.this["changectl-db-password"].secret_id
            version = "latest"
          }
        }
      }
      env {
        name  = "CHANGECTL_BUCKET"
        value = google_storage_bucket.files.name
      }
      env {
        name  = "GOOGLE_OAUTH_CLIENT_ID"
        value = var.google_oauth_client_id
      }
      env {
        name = "GRAFANA_OTLP_ENDPOINT"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.this["changectl-grafana-otlp-endpoint"].secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "GRAFANA_OTLP_TOKEN"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.this["changectl-grafana-otlp-token"].secret_id
            version = "latest"
          }
        }
      }
    }
  }

  # Image is updated outside Terraform via gcloud run deploy (CI).
  lifecycle {
    ignore_changes = [template[0].containers[0].image]
  }

  depends_on = [
    google_artifact_registry_repository.changectl,
    google_secret_manager_secret_iam_member.api_secrets,
    google_secret_manager_secret_version.db_password,
  ]
}

resource "google_cloud_run_v2_service_iam_member" "api_public" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.api.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
