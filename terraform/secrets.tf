locals {
  secret_ids = [
    "changectl-db-password",
    "changectl-google-oauth-client",
    "changectl-auth-secret",
    "changectl-grafana-otlp-endpoint",
    "changectl-grafana-otlp-token",
  ]
}

resource "google_secret_manager_secret" "this" {
  for_each  = toset(local.secret_ids)
  secret_id = each.key

  replication {
    auto {}
  }
}

# Only the DB password is versioned here. The other four are added by hand
# (scripts/bootstrap-project.sh prints the commands) so their values never
# pass through Terraform state.
resource "google_secret_manager_secret_version" "db_password" {
  secret      = google_secret_manager_secret.this["changectl-db-password"].id
  secret_data = var.app_db_password
}
