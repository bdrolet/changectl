#!/bin/bash
# Create the dedicated changectl GCP project, link billing, enable APIs and
# create the Terraform state bucket. Idempotent. Then prints the steps that
# cannot be scripted. Prints no secret values.
#
#   PROJECT_ID=changectl-xxxxxx BILLING_ACCOUNT=XXXXXX-XXXXXX-XXXXXX \
#     scripts/bootstrap-project.sh
set -euo pipefail

: "${PROJECT_ID:?set PROJECT_ID}"
: "${BILLING_ACCOUNT:?set BILLING_ACCOUNT}"
REGION="${REGION:-us-central1}"
STATE_BUCKET="${PROJECT_ID}-tf-state"

if gcloud projects describe "$PROJECT_ID" >/dev/null 2>&1; then
  echo "project $PROJECT_ID exists"
else
  gcloud projects create "$PROJECT_ID" --name=changectl
fi

gcloud billing projects link "$PROJECT_ID" --billing-account="$BILLING_ACCOUNT"

gcloud services enable \
  run.googleapis.com \
  sqladmin.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  storage.googleapis.com \
  iamcredentials.googleapis.com \
  compute.googleapis.com \
  cloudresourcemanager.googleapis.com \
  serviceusage.googleapis.com \
  --project="$PROJECT_ID"

if gcloud storage buckets describe "gs://${STATE_BUCKET}" >/dev/null 2>&1; then
  echo "state bucket gs://${STATE_BUCKET} exists"
else
  gcloud storage buckets create "gs://${STATE_BUCKET}" \
    --project="$PROJECT_ID" \
    --location="$REGION" \
    --uniform-bucket-level-access
fi
gcloud storage buckets update "gs://${STATE_BUCKET}" --versioning

cat <<STEPS

Project $PROJECT_ID is ready. Remaining steps are by hand:

1. OAuth consent screen (Console > APIs & Services > OAuth consent screen,
   project $PROJECT_ID): app name "changectl", user type External, publish to
   production, scopes openid, email, profile.

2. OAuth client (Credentials > Create credentials > OAuth client ID, type Web
   application) with authorized redirect URIs:
     https://changectl.drolet.ai/api/auth/callback/google
     http://localhost:3000/api/auth/callback/google
   Put the client ID in terraform/terraform.tfvars as google_oauth_client_id.

3. Search Console: verify ownership of drolet.ai as the Google account that
   runs terraform apply (needed for the Cloud Run domain mappings).

4. Terraform init:
     cd terraform
     cp terraform.tfvars.example terraform.tfvars   # fill in real values
     terraform init -backend-config="bucket=${STATE_BUCKET}"

5. Create only the secrets first (the services need their versions to exist):
     terraform apply \\
       -target='google_secret_manager_secret.this["changectl-db-password"]' \\
       -target='google_secret_manager_secret.this["changectl-google-oauth-client"]' \\
       -target='google_secret_manager_secret.this["changectl-auth-secret"]' \\
       -target='google_secret_manager_secret.this["changectl-grafana-otlp-endpoint"]' \\
       -target='google_secret_manager_secret.this["changectl-grafana-otlp-token"]'

6. Add the four secret values Terraform does not manage:
     printf '%s' '<oauth client secret>' | gcloud secrets versions add changectl-google-oauth-client --data-file=- --project=$PROJECT_ID
     openssl rand -base64 32 | gcloud secrets versions add changectl-auth-secret --data-file=- --project=$PROJECT_ID
     printf '%s' '<grafana otlp endpoint>' | gcloud secrets versions add changectl-grafana-otlp-endpoint --data-file=- --project=$PROJECT_ID
     printf '%s' '<grafana otlp token>' | gcloud secrets versions add changectl-grafana-otlp-token --data-file=- --project=$PROJECT_ID

7. Full apply (/terraform-plan then /terraform-apply, or terraform apply). The
   services start on a public placeholder image.

8. Set the GitHub repo variable CHANGECTL_PROJECT=$PROJECT_ID so CI deploys
    to this project.

9. Push the real images:
     gh workflow run deploy-api.yml --repo bdrolet/changectl
     gh workflow run deploy-web.yml --repo bdrolet/changectl

10. Migrate the database through the Cloud SQL Auth Proxy:
     cloud-sql-proxy ${PROJECT_ID}:${REGION}:changectl --port 5432 &
     (set the POSTGRES_* env for the owner user "changectl", then)
     python scripts/migrate_db.py
   Leave CHANGECTL_APP_PASSWORD unset: Terraform already created the
   changectl_app role and owns its password, and migrate never changes it.

11. After terraform output web_domain_records / api_domain_records confirm the
    CNAME target (ghs.googlehosted.com), merge the infra repo PR
    "Add changectl DNS records" (bdrolet/infra).
STEPS
