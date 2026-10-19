# Requires drolet.ai to be verified for this project in Search Console (see
# scripts/bootstrap-project.sh). The CNAME records live in the infra repo.
resource "google_cloud_run_domain_mapping" "web" {
  name     = var.web_hostname
  location = var.region

  metadata {
    namespace = var.project_id
  }

  spec {
    route_name = google_cloud_run_v2_service.web.name
  }
}

resource "google_cloud_run_domain_mapping" "api" {
  name     = var.api_hostname
  location = var.region

  metadata {
    namespace = var.project_id
  }

  spec {
    route_name = google_cloud_run_v2_service.api.name
  }
}
