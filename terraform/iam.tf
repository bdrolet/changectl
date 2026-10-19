resource "google_service_account" "api" {
  account_id   = "changectl-api"
  display_name = "changectl API Cloud Run"
}

resource "google_service_account" "web" {
  account_id   = "changectl-web"
  display_name = "changectl web Cloud Run"
}

# --- API runtime SA ---------------------------------------------------------

resource "google_project_iam_member" "api_cloudsql" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.api.email}"
}

resource "google_storage_bucket_iam_member" "api_bucket" {
  bucket = google_storage_bucket.files.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.api.email}"
}

resource "google_secret_manager_secret_iam_member" "api_secrets" {
  for_each = toset([
    "changectl-db-password",
    "changectl-grafana-otlp-endpoint",
    "changectl-grafana-otlp-token",
  ])
  secret_id = google_secret_manager_secret.this[each.key].secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.api.email}"
}

# Signs short-lived URLs for the bucket as itself.
resource "google_service_account_iam_member" "api_token_creator_self" {
  service_account_id = google_service_account.api.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:${google_service_account.api.email}"
}

# --- Web runtime SA ---------------------------------------------------------

resource "google_secret_manager_secret_iam_member" "web_secrets" {
  for_each = toset([
    "changectl-auth-secret",
    "changectl-google-oauth-client",
  ])
  secret_id = google_secret_manager_secret.this[each.key].secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.web.email}"
}

# --- Deployer ---------------------------------------------------------------

resource "google_project_iam_member" "deployer_run_admin" {
  project = var.project_id
  role    = "roles/run.admin"
  member  = "serviceAccount:${var.deployer_service_account}"
}

resource "google_project_iam_member" "deployer_ar_writer" {
  project = var.project_id
  role    = "roles/artifactregistry.writer"
  member  = "serviceAccount:${var.deployer_service_account}"
}

resource "google_service_account_iam_member" "deployer_acts_as" {
  for_each = {
    api = google_service_account.api.name
    web = google_service_account.web.name
  }
  service_account_id = each.value
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${var.deployer_service_account}"
}
