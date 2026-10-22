# Dedicated instance. Public IPv4 with no authorized networks: Cloud Run
# reaches it through the Cloud SQL connector, humans through the Auth Proxy.
# The schema and roles migration is run by hand (see README), not here.
resource "google_sql_database_instance" "changectl" {
  name             = "changectl"
  region           = var.region
  database_version = "POSTGRES_16"

  deletion_protection = true

  settings {
    edition           = "ENTERPRISE" # new projects default to Enterprise Plus, which rejects db-f1-micro
    tier              = var.db_tier
    disk_size         = 10
    disk_type         = "PD_SSD"
    availability_type = "ZONAL"

    # GCP-side guard: refuses deletes from the console, gcloud or the API.
    # The top-level deletion_protection above only stops Terraform itself.
    deletion_protection_enabled = true

    backup_configuration {
      enabled                        = true
      point_in_time_recovery_enabled = false
    }

    ip_configuration {
      ipv4_enabled = true
    }
  }

}

resource "google_sql_database" "changectl" {
  instance = google_sql_database_instance.changectl.name
  name     = "changectl"
}

resource "google_sql_user" "owner" {
  instance = google_sql_database_instance.changectl.name
  name     = "changectl"
  password = var.owner_db_password
}

resource "google_sql_user" "app" {
  instance = google_sql_database_instance.changectl.name
  name     = "changectl_app"
  password = var.app_db_password
}
