# changectl

FastAPI + Postgres change-control service.

## How it works

A Next.js web app talks to a FastAPI API, which stores data in Postgres and files in GCS. Users sign in with Google, and the `users` table is the allowlist: only invited, active users get in. A change moves through the lifecycle initiate, approval, implementation, closed.

## Local dev

```bash
docker compose up -d
python3.13 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt

# Migrate and seed a user (dev@example.test matches .env.local.example).
# Locally the changectl_app role does not exist yet, so migrate creates it with
# CHANGECTL_APP_PASSWORD=app. In the deployed project Terraform creates the role
# and owns its password: run migrate there without CHANGECTL_APP_PASSWORD.
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

### Web app

The Next.js app in `web/` signs in with Google through Auth.js and calls the API at `API_URL` (`http://localhost:8080`, the uvicorn above):

```bash
cd web
npm ci
cp .env.example .env.local   # fill in AUTH_SECRET and the Google OAuth client
npm run dev                  # http://localhost:3000
npm run lint && npm test     # checks
```

### API container

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

## Demo

`scripts/seed_demo.py` fills a demo company: three released documents (Prototype BOM, Cable Assembly Spec, Supplier Spec - Connector), and one change mid-approval. It is idempotent, keyed on change titles.

```bash
SEED_TESA_EMAIL=<email> SEED_BEN_EMAIL=<email> SEED_SECOND_EMAIL=<email> \
  .venv/bin/python scripts/seed_demo.py
```

`SEED_TESA_EMAIL` and `SEED_BEN_EMAIL` are required (the script exits with status 2 without them); `SEED_SECOND_EMAIL` is optional. Walkthrough and pre-demo checklist: [docs/demo-script.md](docs/demo-script.md).

## Compliance posture

The MVP demonstrates unique user identity through Google sign-in, electronic signatures bound to file hashes, an append-only audit trail and revision history. It is not validated and does not claim 21 CFR Part 11 conformance.

## Deployment

Two workflows deploy on pushes to `main` that touch their paths, and both read the GCP project from the `CHANGECTL_PROJECT` repository variable:

- `.github/workflows/deploy-api.yml` runs when the API code changes: it builds the API image, pushes it to Artifact Registry, deploys `changectl-api` to Cloud Run and curls `/health`.
- `.github/workflows/deploy-web.yml` runs when `web/` changes: it builds the web image, pushes it, deploys `changectl-web` to Cloud Run and checks `/signin` returns 200.

Either can also be run by hand with `gh workflow run <file> --repo bdrolet/changectl`.

## First-time setup

`scripts/bootstrap-project.sh` creates the dedicated GCP project, links billing, enables the APIs and creates the Terraform state bucket, then prints the remaining by-hand steps: OAuth client, secrets, Terraform apply, the first deploys of both workflows, and the database migration. Terraform creates the `changectl_app` Cloud SQL user and owns its password, so the migration there runs without `CHANGECTL_APP_PASSWORD`.
