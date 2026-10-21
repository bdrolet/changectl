#!/bin/bash
# Populate .env from Secret Manager + terraform/terraform.tfvars for running
# uvicorn directly. Run from the repo root. Start the Cloud SQL Auth Proxy first
# (see README); this points the app at it on localhost:5432.
set -e
PROJECT="${CHANGECTL_PROJECT:?set CHANGECTL_PROJECT to the GCP project id}"
secret() { gcloud secrets versions access latest --secret="$1" --project="$PROJECT"; }
tfvar() {
  [ -f terraform/terraform.tfvars ] || return 0
  grep "^$1" terraform/terraform.tfvars | sed 's/.*= *"\(.*\)"/\1/' || true
}

cat > .env <<ENVEOF
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=changectl
POSTGRES_USER=changectl_app
POSTGRES_PASSWORD=$(secret changectl-db-password)
CHANGECTL_BUCKET=${PROJECT}-files
GOOGLE_OAUTH_CLIENT_ID=$(tfvar google_oauth_client_id)
ENVEOF
echo ".env written"
