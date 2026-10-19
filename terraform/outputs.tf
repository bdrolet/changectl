output "web_url" {
  value = google_cloud_run_v2_service.web.uri
}

output "api_url" {
  value = google_cloud_run_v2_service.api.uri
}

output "sql_connection_name" {
  value = google_sql_database_instance.changectl.connection_name
}

output "bucket" {
  value = google_storage_bucket.files.name
}

# Confirm these match the CNAME targets in the infra repo
# (expected: ghs.googlehosted.com.).
output "web_domain_records" {
  value = google_cloud_run_domain_mapping.web.status[0].resource_records
}

output "api_domain_records" {
  value = google_cloud_run_domain_mapping.api.status[0].resource_records
}
