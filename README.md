# changectl

FastAPI + Postgres change-control service.

## How it works

A Next.js web app talks to a FastAPI API, which stores data in Postgres and files in GCS. Users sign in with Google, and the `users` table is the allowlist: only invited, active users get in. A change moves through the lifecycle initiate, approval, implementation, closed.

## Local dev

```bash
docker compose up -d
python3.13 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt

# Migrate and seed a user (dev@example.test matches .env.local.example)
export POSTGRES_HOST=localhost POSTGRES_PORT=5434 POSTGRES_DB=changectl POSTGRES_USER=changectl POSTGRES_PASSWORD=changectl
CHANGECTL_APP_PASSWORD=app .venv/bin/python scripts/migrate_db.py
.venv/bin/python scripts/add_user.py dev@example.test "Dev User" --doc-manager

# Run the API directly with the dev bypass (K_SERVICE unset)
CHANGECTL_LOCAL_STORAGE=/tmp/changectl-storage CHANGECTL_DEV_USER_EMAIL=dev@example.test \
  GOOGLE_OAUTH_CLIENT_ID=unused-locally .venv/bin/uvicorn api.main:app --port 8080

# In another shell: smoke it (add --token <google id token> for a real deployment)
.venv/bin/python scripts/test-api-local.py

# Tests
CHANGECTL_TEST_DSN=postgresql://changectl:changectl@localhost:5434/changectl .venv/bin/pytest -q
```

**`scripts/migrate_db.py` runs only through a direct Postgres connection (local compose or the Cloud SQL Auth Proxy), never through the pg8000 connector path, because the connector cannot run multi-statement SQL files.**

To run the container instead of uvicorn:

```bash
cp .env.local.example .env.local
docker build -t changectl-api .
docker run --rm -p 8080:8080 --env-file .env.local changectl-api
```

To run uvicorn against a deployed database, start the Cloud SQL Auth Proxy and write `.env`:

```bash
cloud-sql-proxy --port 5432 "$CHANGECTL_PROJECT:us-central1:<instance>" &
CHANGECTL_PROJECT=<project-id> scripts/fetch-env.sh
(set -a; source .env; set +a; .venv/bin/uvicorn api.main:app --port 8080)
```

## Deployment

Pushing to `main` deploys the API through `.github/workflows/deploy-api.yml`: it builds the image, pushes it to Artifact Registry, deploys `changectl-api` to Cloud Run and curls `/health`. The workflow reads the GCP project from the `CHANGECTL_PROJECT` repository variable.

## First-time setup

`scripts/bootstrap-project.sh` creates the GCP project and its infrastructure. It is forthcoming (Task 16).
