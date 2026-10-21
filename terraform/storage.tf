resource "google_storage_bucket" "files" {
  name                        = "${var.project_id}-files"
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"

  versioning {
    enabled = true
  }

  soft_delete_policy {
    retention_duration_seconds = 2592000 # 30 days
  }
}
