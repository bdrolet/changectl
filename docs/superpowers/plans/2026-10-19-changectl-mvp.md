# changectl MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A deployable change-control web app: upload controlled documents, run a change through initiate → approval → implementation → closed with electronic approvals, release numbered revisions, search them, and keep an append-only audit trail.

**Architecture:** A FastAPI service (`api/`) over Postgres and a GCS bucket, verifying Google ID tokens against an allowlist held in the `users` table; a Next.js app (`web/`) that signs users in with Google via Auth.js and proxies every API call server-side with that token. Both run as Cloud Run services in a dedicated GCP project, provisioned by Terraform in `terraform/`, deployed by GitHub Actions on push to `main`.

**Tech Stack:** Python 3.13, FastAPI, psycopg 3 (local) / pg8000 via Cloud SQL connector (Cloud Run), pymupdf, python-docx, openpyxl, google-auth, google-cloud-storage, OpenTelemetry; Next.js 16, React 19, TypeScript, Tailwind 4, Auth.js v5; Terraform ~1.5; Postgres 16.

**Spec:** `docs/superpowers/specs/2026-10-19-changectl-mvp-design.md` (requirements it cites: `~/src/consulting/docs/case-studies/tesa/requirements.md`)

## Global Constraints

- Python 3.13; ruff `line-length = 100`, `select = ["E","F","I"]`; mypy on `clients/ services/ repo/ models/ api/`. Copy `pyproject.toml` from `~/src/tasks` and change names.
- Layer rules from the spec §6: `clients/` I/O only; `repo/` takes an open connection and never opens one; `services/` no HTTP; `api/routers/` thin.
- DB access through `clients/db.py::get_conn()` copied from `~/src/tasks/clients/db.py` with the pgvector branches removed. Locally psycopg 3 with `dict_row`; on Cloud Run pg8000 via the connector. Every SQL string must run on both (use `%s` placeholders only).
- Two DB roles: `changectl_owner` (migrations) and `changectl_app` (runtime). `changectl_app` has `INSERT, SELECT` on `events` and no `UPDATE`/`DELETE` on it.
- Accepted uploads: `application/pdf`, `application/vnd.openxmlformats-officedocument.wordprocessingml.document`, `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`. Max 25 MB (`26_214_400` bytes). Type is decided by magic bytes, not the declared header.
- Extracted text capped at 2 MB (`2_097_152` chars). Signed download URLs expire after 10 minutes. Sessions last 8 hours.
- Roles: `engineering | operations | quality | other`. Statuses: `initiate | approval | implementation | closed`. Change numbers display as `CHG-0001` (`CHG-` + 4-digit zero-padded `changes.number`).
- Metrics prefixed `changectl_`. Service names `changectl-api`, `changectl-web`. Hostnames `changectl.drolet.ai`, `api.changectl.drolet.ai`.
- No real person's email in any committed file. Seed and tfvars carry them; `*.tfvars` and `.env` are gitignored.
- UI copy never claims compliance. The word "compliant" does not appear in `web/`.
- Every mutating API route writes exactly one `events` row inside the same transaction as its data change.

## Review Focus

1. A file whose extension or declared `Content-Type` says PDF but whose bytes are not (a renamed `.exe`, an HTML error page): the API rejects it with 415 and stores nothing. Test in Task 13.
2. A pending approver who is deactivated while a change sits in `approval`: the change could never complete. `PATCH /users/{id}` with `deactivated: true` returns 409 naming the open change numbers instead. Test in Task 12.
3. Two approve clicks on the same change by the same user (double submit): one `approvals` row, second call returns 200 with the existing approval, not 500 from a unique violation. Test in Task 8.
4. A search query with no lexemes (`"the"`, `"&&"`, `""`): falls back to `ILIKE` on title, never 500. Test in Task 9.
5. A release-file replacement whose type differs from the signed file (xlsx signed, pdf uploaded): 409, nothing moved. Test in Task 8.

---

## File structure

```
pyproject.toml  requirements.txt  requirements-dev.txt  docker-compose.yml  Dockerfile  .dockerignore
clients/db.py            connection (copied from tasks)
clients/otel.py          telemetry (copied from tasks, prefix changectl_)
clients/storage.py       Storage protocol: GcsStorage, LocalStorage
clients/google_id_token.py  verify_id_token(token, audience) -> Claims
repo/schema.sql  repo/roles.sql
repo/users.py  repo/documents.py  repo/changes.py  repo/events.py
services/extract.py      sniff_type(data) -> str|None ; extract_text(content_type, data) -> str|None
services/lifecycle.py    every state transition, raises LifecycleError
services/search.py       search_documents(conn, q) -> list[dict]
models/errors.py         LifecycleError(code, detail)
api/main.py  api/auth.py  api/errors.py  api/schemas.py
api/routers/{me,users,changes,documents,audit}.py
scripts/migrate_db.py  scripts/seed_demo.py  scripts/fetch-env.sh  scripts/test-api-local.py  scripts/bootstrap-project.sh
terraform/{versions,variables,cloudsql,storage,secrets,iam,api,web,domains,outputs}.tf  terraform.tfvars.example
web/  (Next.js app; see Task 17 for its tree)
.github/workflows/{ci,deploy-api,deploy-web}.yml
tests/  (pytest; DB tests skip without CHANGECTL_TEST_DSN)
```

---

## Phase 1 — Scaffold and data layer

### Task 1: Python scaffold, local Postgres, CI

**Files:**
- Create: `pyproject.toml`, `requirements.txt`, `requirements-dev.txt`, `docker-compose.yml`, `.gitignore`, `clients/__init__.py`, `clients/db.py`, `clients/otel.py`, `repo/__init__.py`, `services/__init__.py`, `models/__init__.py`, `api/__init__.py`, `tests/conftest.py`, `.github/workflows/ci.yml`, `README.md`
- Test: `tests/test_db.py`

**Interfaces:**
- Produces: `clients.db.get_conn()`; pytest fixtures `raw_conn` (empty schema) and `db_conn` (schema + roles applied, from Task 2 on); env `CHANGECTL_TEST_DSN`.

- [ ] **Step 1: Copy and trim the shared files.** `pyproject.toml` from `~/src/tasks` (mypy paths without `handlers/`, `main.py`); `clients/db.py` from `~/src/tasks/clients/db.py` deleting the pgvector list branch in `_adapt_params`, default db `changectl`; `clients/otel.py` verbatim, then rename every `asana_` instrument to `changectl_` and keep only `api_requests` plus a new counter `changectl_uploads` (`uploads`). `requirements.txt`: `fastapi`, `uvicorn[standard]`, `psycopg>=3.1`, `pg8000>=1.31`, `cloud-sql-python-connector>=1.7`, `google-auth>=2.30`, `google-cloud-storage>=2.16`, `pymupdf>=1.24`, `python-docx>=1.1`, `openpyxl>=3.1`, `python-multipart>=0.0.9`, `opentelemetry-sdk>=1.24`, `opentelemetry-exporter-otlp-proto-http>=1.24`, `python-dotenv>=1.0`. `requirements-dev.txt`: `-r requirements.txt`, `pytest`, `httpx`, `ruff`, `mypy`.
- [ ] **Step 2: `docker-compose.yml`** like `~/src/finances/docker-compose.yml`: image `postgres:16`, db/user/password `changectl`, host port `5434`, volume `changectl_pgdata`.
- [ ] **Step 3: `tests/conftest.py`** modelled on `~/src/finances/tests/conftest.py`: `TEST_DSN = os.environ.get("CHANGECTL_TEST_DSN")`; fixture `raw_conn` (psycopg 3, `dict_row`, `DROP SCHEMA public CASCADE; CREATE SCHEMA public;`, skip when unset); fixture `db_conn` applies `repo/schema.sql` then `repo/roles.sql` (files arrive in Task 2; until then the fixture applies only what exists). Also the tasks-style autouse fixture that deletes `CLOUD_SQL_CONNECTION_NAME` and `POSTGRES_*` from the environment.
- [ ] **Step 4: Write `tests/test_db.py::test_select_one`** — with `raw_conn`, `conn.execute("SELECT 1 AS one").fetchone() == {"one": 1}`.
- [ ] **Step 5: Run** `docker compose up -d && CHANGECTL_TEST_DSN=postgresql://changectl:changectl@localhost:5434/changectl .venv/bin/pytest -q`. Expected: 1 passed.
- [ ] **Step 6: `.github/workflows/ci.yml`** from `~/src/tasks/.github/workflows/ci.yml`, adding a `postgres:16` service container and exporting `CHANGECTL_TEST_DSN` to the pytest step; terraform validate step kept (it will no-op until Task 16). Add a second job `web` that runs `npm ci && npm run lint && npm run build` in `web/` only when `web/**` changed (`dorny/paths-filter` or `on.push.paths` on a separate workflow; builder's choice).
- [ ] **Step 7: Commit** `chore: python scaffold, local postgres, CI`.

### Task 2: Schema, roles, migration script

**Files:**
- Create: `repo/schema.sql`, `repo/roles.sql`, `scripts/migrate_db.py`
- Test: `tests/test_schema.py`

**Interfaces:**
- Produces: the tables in spec §7 exactly, with these pinned details: all ids `uuid DEFAULT gen_random_uuid()`; `changes.number serial UNIQUE`; enums `user_role`, `change_status`, `approval_decision`; `revisions.search tsvector GENERATED ALWAYS AS (to_tsvector('english', coalesce(extracted_text,''))) STORED` with a GIN index; `documents.title_search tsvector GENERATED ... to_tsvector('english', title)` with GIN, plus `CREATE EXTENSION IF NOT EXISTS pg_trgm` and a GIN trigram index on `documents.title`; partial unique index `approvals (change_id, user_id) WHERE voided_at IS NULL`; `events` with `at timestamptz DEFAULT now()`; FK `revisions.change_id → changes`, `documents.current_revision_id → revisions` (deferrable). `roles.sql` creates `changectl_app` if missing (password from `:app_password` psql variable), grants `SELECT, INSERT, UPDATE, DELETE` on all tables except `events`, which gets `SELECT, INSERT` only, and `USAGE` on sequences.
- Produces: `python scripts/migrate_db.py` applies `schema.sql` (idempotent: `CREATE TABLE IF NOT EXISTS`, `DO $$ ... $$` guards for enums) then `roles.sql` using `CHANGECTL_APP_PASSWORD`.

- [ ] **Step 1: Write failing tests** in `tests/test_schema.py`: `test_tables_exist` (query `information_schema.tables` for the nine table names); `test_events_append_only` — connect as `changectl_app` (fixture creates the role with password `app`), `INSERT` succeeds, `UPDATE events SET action='x'` raises `psycopg.errors.InsufficientPrivilege`, `DELETE` likewise; `test_schema_idempotent` — apply `schema.sql` twice without error; `test_one_live_approval_per_user` — two inserts into `approvals` for the same `(change_id, user_id)` with `voided_at NULL` raise `UniqueViolation`, a third with `voided_at` set succeeds.
- [ ] **Step 2: Run** `pytest tests/test_schema.py -v`. Expected: FAIL (no schema file).
- [ ] **Step 3: Write `repo/schema.sql` and `repo/roles.sql`** per the Interfaces block; write `scripts/migrate_db.py` with `main() -> None` that opens `clients.db.get_conn()` and executes both files in order.
- [ ] **Step 4: Run** the tests. Expected: PASS.
- [ ] **Step 5: Commit** `feat: schema, app role, migrate script`.

### Task 3: repo — users and events

**Files:**
- Create: `repo/users.py`, `repo/events.py`
- Test: `tests/test_repo_users.py`, `tests/test_repo_events.py`

**Interfaces:**
- Produces (`repo/users.py`): `insert(conn, *, email: str, name: str, role: str, is_doc_manager: bool, invited_by: str | None) -> dict`; `by_email(conn, email: str) -> dict | None`; `by_id(conn, user_id: str) -> dict | None`; `list_all(conn) -> list[dict]`; `set_google_sub(conn, user_id: str, sub: str) -> None`; `update(conn, user_id: str, *, role: str | None = None, is_doc_manager: bool | None = None, deactivated: bool | None = None) -> dict` (sets/clears `deactivated_at`). Emails stored lower-cased; `by_email` lower-cases its argument.
- Produces (`repo/events.py`): `record(conn, *, actor_user_id: str | None, entity_type: str, entity_id: str, action: str, detail: dict | None = None) -> dict`; `for_entity(conn, entity_type: str, entity_id: str) -> list[dict]` newest first; `for_change(conn, change_id: str) -> list[dict]` — events whose `entity_type='change' AND entity_id=change_id` **or** whose `detail->>'change_id'` equals it, newest first.

- [ ] **Step 1: Write failing tests:** `test_insert_and_by_email_case_insensitive`, `test_update_deactivates_and_reactivates` (deactivated_at set then null), `test_record_and_for_entity_order` (two events, newest first), `test_for_change_includes_detail_linked` (a `revision` event with `detail={"change_id": ...}` shows up).
- [ ] **Step 2: Run** them. Expected: FAIL, modules missing.
- [ ] **Step 3: Implement** both modules in the `~/src/tasks/repo/tasks.py` style (plain SQL, `%s`, `RETURNING *`, `json.dumps` for jsonb params).
- [ ] **Step 4: Run** tests. Expected: PASS.
- [ ] **Step 5: Commit** `feat: users and events repo`.

### Task 4: repo — documents and revisions

**Files:**
- Create: `repo/documents.py`
- Test: `tests/test_repo_documents.py`

**Interfaces:**
- Produces: `insert_document(conn, *, title: str, created_by: str) -> dict`; `document(conn, document_id: str) -> dict | None`; `insert_revision(conn, *, document_id: str, change_id: str, original_filename: str, content_type: str, byte_size: int, sha256: str, gcs_key: str, extracted_text: str | None, uploaded_by: str) -> dict`; `revision(conn, revision_id: str) -> dict | None`; `revisions_for_document(conn, document_id: str) -> list[dict]` (released first by `revision_number DESC NULLS FIRST`); `revisions_for_change(conn, change_id: str) -> list[dict]`; `delete_revision(conn, revision_id: str) -> None`; `set_release_file(conn, revision_id: str, *, gcs_key: str, sha256: str, content_type: str, byte_size: int, original_filename: str, extracted_text: str | None, redline_gcs_key: str, redline_sha256: str) -> dict`; `release(conn, revision_id: str, *, revision_number: int, released_by: str, released_at) -> dict`; `supersede_current(conn, document_id: str, new_revision_id: str, at) -> None` (stamps `superseded_at` on the old current and points `current_revision_id` at the new one); `next_revision_number(conn, document_id: str) -> int` (max released + 1, or 1); `pending_revision_exists(conn, document_id: str) -> bool` (a revision with `released_at IS NULL` whose change is not closed).

- [ ] **Step 1: Write failing tests:** `test_next_revision_number_starts_at_one`, `test_release_and_supersede` (after releasing rev 2, old current has `superseded_at`, document points at new), `test_pending_revision_exists_true_until_release`.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat: documents and revisions repo`.

### Task 5: repo — changes, approvers, approvals, comments

**Files:**
- Create: `repo/changes.py`
- Test: `tests/test_repo_changes.py`

**Interfaces:**
- Produces: `insert(conn, *, title, description, reason, justification, created_by) -> dict`; `get(conn, change_id) -> dict | None`; `list_by_status(conn, status: str | None) -> list[dict]` (newest first, includes `number`); `update_fields(conn, change_id, *, title=None, description=None, reason=None, justification=None) -> dict`; `set_status(conn, change_id, status: str, *, at) -> dict` (also stamps `submitted_at`/`approved_at`/`closed_at` for the matching status); `set_cutin(conn, change_id, cutin_date) -> None`; `link_revision(conn, change_id, revision_id) -> None`; `unlink_revision(conn, change_id, revision_id) -> None`; `set_approvers(conn, change_id, user_ids: list[str], added_by: str) -> None` (replace whole set); `approvers(conn, change_id) -> list[dict]` (joined with users: id, name, email, role); `insert_approval(conn, *, change_id, user_id, google_sub, email, decision: str, comment: str | None, file_sha256s: list[str]) -> dict`; `live_approvals(conn, change_id) -> list[dict]` (`voided_at IS NULL`); `void_approvals(conn, change_id, reason: str, at) -> int`; `insert_comment(conn, *, change_id, user_id, body) -> dict`; `comments(conn, change_id) -> list[dict]` oldest first; `open_changes_awaiting(conn, user_id) -> list[dict]` — changes in `approval` where the user is an approver with no live `approved` row.
- `display_number(number: int) -> str` returns `CHG-0001`-style (lives in `models/__init__.py` or `models/display.py`; pure).

- [ ] **Step 1: Write failing tests:** `test_display_number_pads_four`, `test_set_approvers_replaces_set`, `test_void_approvals_returns_count_and_sets_reason`, `test_open_changes_awaiting_excludes_signed`.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat: changes repo`.

## Phase 2 — Services

### Task 6: File type sniffing and text extraction

**Files:**
- Create: `services/extract.py`
- Test: `tests/test_extract.py`

**Interfaces:**
- Produces: `PDF = "application/pdf"`, `DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"`, `XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"`, `ACCEPTED = frozenset({PDF, DOCX, XLSX})`; `sniff_type(data: bytes) -> str | None` — `%PDF-` prefix → PDF; `PK\x03\x04` prefix → open as zip and return DOCX if `word/document.xml` is a member, XLSX if `xl/workbook.xml`, else `None`; anything else `None`. `extract_text(content_type: str, data: bytes) -> str | None` — pymupdf page text joined by `\n`, python-docx paragraphs and table cells joined by `\n`, openpyxl every non-empty cell `str()` joined by `\t` per row and `\n` per row across all sheets; result truncated to `MAX_TEXT_CHARS = 2_097_152`; returns `None` when the library raises (encrypted PDF, corrupt zip) or the text is empty after `strip()`.

- [ ] **Step 1: Write failing tests** that build fixtures in-test: `test_sniff_pdf` (bytes from a one-page pymupdf doc), `test_sniff_docx_vs_xlsx` (python-docx / openpyxl `save` to `BytesIO`), `test_sniff_rejects_zip_without_office_parts` and `test_sniff_rejects_html`, `test_extract_xlsx_cells_tab_separated` (cells `A1="Part"`, `B1="J4"` → `"Part\tJ4"` in the text), `test_extract_docx_includes_table_cells`, `test_extract_encrypted_pdf_returns_none` (pymupdf `save(encryption=PDF_ENCRYPT_AES_256, user_pw="x")`), `test_extract_truncates_at_cap` (monkeypatch `MAX_TEXT_CHARS = 10`).
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat: file sniffing and text extraction`.

### Task 7: Storage client

**Files:**
- Create: `clients/storage.py`
- Test: `tests/test_storage.py`

**Interfaces:**
- Produces: `class Storage(Protocol)`: `put(key: str, data: bytes, content_type: str) -> None`; `get(key: str) -> bytes`; `signed_url(key: str, filename: str, minutes: int = 10) -> str`. `class LocalStorage(root: Path)` writes files under `root/key` and returns `signed_url` as `file://` + path (tests and local dev). `class GcsStorage(bucket: str)` uses `google.cloud.storage`; `signed_url` uses `blob.generate_signed_url(version="v4", expiration=timedelta(minutes=minutes), response_disposition=f'attachment; filename="{filename}"', service_account_email=<ADC SA>, access_token=<ADC token>)` — the IAM-signing form, no key file. `def from_env() -> Storage`: `CHANGECTL_BUCKET` set → `GcsStorage`, else `LocalStorage(Path(os.environ.get("CHANGECTL_LOCAL_STORAGE", ".storage")))`. `def object_key(document_id: str, revision_id: str, filename: str) -> str` returns `documents/{document_id}/{revision_id}/{safe_filename}` where `safe_filename` keeps `[A-Za-z0-9._-]` and replaces the rest with `_`.

- [ ] **Step 1: Write failing tests:** `test_local_roundtrip` (`put` then `get` equal bytes), `test_object_key_sanitizes` (`"BOM v2 (final).xlsx"` → `documents/d/r/BOM_v2__final_.xlsx`), `test_from_env_local_without_bucket`.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement** (GCS path untested beyond import). **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat: storage client with local and GCS backends`.

### Task 8: Lifecycle service

**Files:**
- Create: `models/errors.py`, `services/lifecycle.py`
- Test: `tests/test_lifecycle.py`

**Interfaces:**
- Consumes: Tasks 3, 4, 5, 6, 7.
- Produces (`models/errors.py`): `class LifecycleError(Exception)` with `code: str` and `detail: str`; codes used: `not_found`, `forbidden`, `wrong_status`, `locked`, `self_approval`, `not_an_approver`, `no_approvers`, `no_revisions`, `invalid_file`, `too_large`, `type_mismatch`, `document_busy`, `cutin_required`.
- Produces (`services/lifecycle.py`), every function takes `conn` first and an `actor: dict` (a users row) and commits nothing (the caller owns the transaction); each writes its `events` row through `repo.events.record`:
  - `create_change(conn, actor, *, title, description, reason, justification) -> dict` — status `initiate`, event `change.created`.
  - `update_change(conn, actor, change_id, **fields) -> dict` — only in `initiate`, only by `created_by` (else `forbidden`), event `change.updated` with the changed field names.
  - `attach_revision(conn, actor, change_id, *, filename: str, data: bytes, storage: Storage, document_id: str | None = None, title: str | None = None) -> dict` — `initiate` only; `len(data) > MAX_UPLOAD_BYTES (26_214_400)` → `too_large`; `sniff_type(data)` not in `ACCEPTED` → `invalid_file`; `document_id` given and `pending_revision_exists` → `document_busy`; neither `document_id` nor `title` → `invalid_file`; creates the document when needed, stores bytes at `object_key(...)`, extracts text, inserts the revision, links it, event `revision.attached` with `detail={"change_id":..., "document_id":..., "sha256":...}`. Returns the revision row.
  - `remove_revision(conn, actor, change_id, revision_id) -> None` — `initiate` only; deletes the revision row (object left in the bucket); if the document now has no revisions at all, deletes the document too. Event `revision.removed`.
  - `set_approvers(conn, actor, change_id, user_ids: list[str]) -> list[dict]` — `initiate` only; `actor["id"]` in the list → `self_approval`; any id not an active user → `not_found`. Event `change.approvers_set`.
  - `submit(conn, actor, change_id) -> dict` — `initiate` only, creator only; no approvers → `no_approvers`; no revisions → `no_revisions`; status → `approval`, event `change.submitted`.
  - `approve(conn, actor, change_id, *, google_sub: str, comment: str | None) -> dict` — `approval` only; actor not in approvers → `not_an_approver`; actor is creator → `self_approval`; an existing live `approved` row by this user → return it unchanged (idempotent); else insert with `file_sha256s` = sorted sha256 of every attached revision, event `change.approved`; if every approver now has a live approval, status → `implementation` and event `change.approval_complete`.
  - `request_changes(conn, actor, change_id, *, google_sub: str, comment: str) -> dict` — `approval` only, approver only, comment required; inserts a `changes_requested` row, voids all live approvals with reason `changes_requested_by:{actor email}`, status → `initiate`, event `change.changes_requested`.
  - `replace_release_file(conn, actor, change_id, revision_id, *, filename, data, storage) -> dict` — `implementation` only, doc manager only; sniffed type must equal the revision's `content_type` else `type_mismatch`; same size/type checks as attach; moves the signed file's key and sha into `redline_*`, stores the new bytes under a new key, re-extracts; event `revision.release_file_replaced` with both hashes.
  - `release(conn, actor, change_id, *, cutin_date: date) -> dict` — `implementation` only, doc manager only; for each attached revision: `next_revision_number`, `repo.documents.release`, `supersede_current`; `set_cutin`; status → `closed`; one event `change.released` with `detail={"revisions": [{"revision_id", "document_id", "revision_number", "sha256", "redline_sha256"}], "cutin_date": ...}`.
  - `add_comment(conn, actor, change_id, body: str) -> dict` — any status, any active user; event `change.commented`.
- Produces: `MAX_UPLOAD_BYTES = 26_214_400`.

- [ ] **Step 1: Write failing tests** using `db_conn`, `LocalStorage(tmp_path)`, helper fixtures `users` (creator engineering, approver_a quality, approver_b operations, docmgr with `is_doc_manager`) and `xlsx_bytes`/`pdf_bytes`: `test_full_initial_release_flow` (create → attach xlsx with title → set two approvers → submit → both approve → status `implementation` → release → status `closed`, `revision_number == 1`, document `current_revision_id` set, events contain `change.released`); `test_cannot_approve_own_change` (creator added as approver fails at `set_approvers` with `self_approval`); `test_submit_requires_approvers_and_revisions`; `test_approve_is_idempotent` (second approve returns same id, one live row — Review Focus 3); `test_request_changes_voids_and_reopens` (status `initiate`, `void_approvals` count 1, reason string); `test_locked_after_submit` (`update_change` → `wrong_status`); `test_attach_rejects_oversize_and_bad_type` (`too_large`, `invalid_file` for `b"<html>"`); `test_document_busy_blocks_second_pending_revision`; `test_replace_release_file_type_mismatch` (xlsx revision, pdf upload → `type_mismatch` — Review Focus 5); `test_revision_flow_supersedes` (release rev 1, new change attaching a redline to the same document, release → rev 2 current, rev 1 `superseded_at` set); `test_release_requires_doc_manager`.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement** `models/errors.py` then `services/lifecycle.py`. **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat: change lifecycle service`.

### Task 9: Search service

**Files:**
- Create: `services/search.py`
- Test: `tests/test_search.py`

**Interfaces:**
- Produces: `search_documents(conn, q: str, *, limit: int = 50) -> list[dict]` — rows: `document_id, title, current_revision_id, revision_number, released_at, released_by_name, original_filename, rank`. Only documents with `current_revision_id IS NOT NULL`. When `q.strip()` is empty → all current documents by `released_at DESC`. Else build `websearch_to_tsquery('english', q)`; if `numnode(query) = 0` (no lexemes) → `ILIKE '%q%'` on title; else `WHERE d.title_search @@ query OR r.search @@ query` ranked by `ts_rank(d.title_search, query) * 2 + ts_rank(r.search, query)` desc, where `r` is the current revision. `document_detail(conn, document_id) -> dict | None` — document plus `revisions` (each with its change `number`, `title`, `status`, `cutin_date`, approvals' approver names and `signed_at`).

- [ ] **Step 1: Write failing tests:** `test_search_matches_extracted_text` (released xlsx containing `J4 connector` found by `connector`); `test_search_excludes_unreleased`; `test_search_title_weighted_first`; `test_search_stopwords_fall_back_to_ilike` (`q="the"` with a title `"The BOM"` → found, no exception — Review Focus 4); `test_search_empty_lists_all_current`; `test_document_detail_lists_revisions_with_change_numbers`.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat: document search`.

## Phase 3 — API

### Task 10: Google ID token verification and the user dependency

**Files:**
- Create: `clients/google_id_token.py`, `api/auth.py`
- Test: `tests/test_auth.py`

**Interfaces:**
- Produces (`clients/google_id_token.py`): `@dataclass Claims(sub: str, email: str, email_verified: bool, name: str | None)`; `verify_id_token(token: str, audience: str) -> Claims` wrapping `google.oauth2.id_token.verify_oauth2_token(token, google.auth.transport.requests.Request(), audience)`; raises `ValueError` on any failure (library already does).
- Produces (`api/auth.py`): `current_user(request: Request, conn=Depends(get_conn_dep)) -> dict` FastAPI dependency: missing/malformed `Authorization: Bearer` → 401; `verify_id_token` `ValueError` → 401; `email_verified` false → 401; no `users` row for the email, or `deactivated_at` set → 403 `{"detail": "not_invited"}`; row has `google_sub` and it differs from `claims.sub` → 403 `{"detail": "identity_mismatch"}`; row has no `google_sub` → `set_google_sub` and event `user.first_sign_in`; sets `request.state.google_sub = claims.sub`; returns the user row. `require_doc_manager(user=Depends(current_user)) -> dict` → 403 `{"detail": "doc_manager_required"}`. Audience from env `GOOGLE_OAUTH_CLIENT_ID`. **Dev bypass:** when `K_SERVICE` is unset and `CHANGECTL_DEV_USER_EMAIL` is set, `current_user` skips token verification and loads that email (sub `dev`). Never active on Cloud Run.
- Produces (`api/deps.py` or inside `api/auth.py`): `get_conn_dep()` yields a `clients.db.get_conn()` connection, commits on success, rolls back on exception, closes always.

- [ ] **Step 1: Write failing tests** with `monkeypatch.setattr("api.auth.verify_id_token", fake)` and a TestClient on a minimal app exposing `/me`: `test_missing_bearer_401`, `test_bad_token_401`, `test_unverified_email_401`, `test_unknown_email_403_not_invited`, `test_deactivated_403`, `test_first_sign_in_stores_sub_and_event`, `test_sub_mismatch_403`, `test_dev_bypass_only_off_cloud_run` (with `K_SERVICE` set the bypass is ignored → 401).
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat: Google ID token auth with allowlist`.

### Task 11: API app, error translation, schemas, `/me`

**Files:**
- Create: `api/main.py`, `api/errors.py`, `api/schemas.py`, `api/routers/me.py`
- Test: `tests/test_api_main.py`

**Interfaces:**
- Produces: `app` in `api/main.py` modelled on `~/src/tasks/api/main.py` (logging `force=True`, `otel.setup_telemetry(os.environ.get("K_SERVICE", "changectl-api-local"))`, request-metrics middleware, `GET /health` → `{"status":"ok"}`), routers mounted from `api.routers`. `api/errors.py::install(app)` registers an exception handler mapping `LifecycleError.code` → status: `not_found` 404, `forbidden`/`self_approval`/`not_an_approver` 403, `wrong_status`/`locked`/`document_busy`/`type_mismatch` 409, `too_large` 413, `invalid_file` 415, `no_approvers`/`no_revisions`/`cutin_required` 422; body `{"detail": code, "message": detail}`. `api/schemas.py` holds the pydantic response models: `UserOut`, `ChangeSummary` (whose `number` is the display string from `display_number`, e.g. `CHG-0001`), `ChangeDetail` (fields, `revisions`, `approvers` each with `state: "signed"|"pending"|"changes_requested"`, `approvals`, `comments`, `events`, `waiting_on: list[str]`), `RevisionOut`, `DocumentSummary`, `DocumentDetail`, `EventOut`. `GET /me` returns `UserOut`.
- Produces: tests get an `api_client` fixture (TestClient + `db_conn` + dev-bypass env + dependency override of `get_conn_dep` to the test connection) and a helper `as_user(email)` that flips `CHANGECTL_DEV_USER_EMAIL`.

- [ ] **Step 1: Write failing tests:** `test_health`, `test_me_returns_user`, `test_lifecycle_error_maps_to_status` (raise `LifecycleError("too_large", "x")` from a test route → 413 with `detail == "too_large"`).
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat: API app skeleton and /me`.

### Task 12: Users router

**Files:**
- Create: `api/routers/users.py`
- Test: `tests/test_api_users.py`

**Interfaces:**
- Produces: `GET /users` (any user; active and deactivated, with a `deactivated: bool`); `POST /users` doc manager: body `{email, name, role, is_doc_manager}` → 201 `UserOut`, duplicate email → 409; event `user.invited`. `PATCH /users/{id}` doc manager: body any of `{role, is_doc_manager, deactivated}`; setting `deactivated: true` for a user who is a pending approver on any change in `approval` → 409 `{"detail": "pending_approver", "changes": ["CHG-0004", ...]}` (Review Focus 2); a doc manager cannot remove their own `is_doc_manager` if they are the last one → 409 `last_doc_manager`; event `user.updated`.

- [ ] **Step 1: Write failing tests:** `test_invite_requires_doc_manager`, `test_invite_lowercases_and_dedupes`, `test_deactivate_pending_approver_409_lists_changes`, `test_last_doc_manager_cannot_demote_self`.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat: users router`.

### Task 13: Changes router

**Files:**
- Create: `api/routers/changes.py`
- Test: `tests/test_api_changes.py`

**Interfaces:**
- Consumes: Task 8 functions one-to-one.
- Produces the routes in spec §9 under `/changes`: `POST /changes` 201; `GET /changes?status=`; `GET /changes/{id}` → `ChangeDetail`; `PATCH /changes/{id}`; `POST /changes/{id}/revisions` multipart fields `file` (required), `document_id` or `title`; `DELETE /changes/{id}/revisions/{rid}` 204; `PUT /changes/{id}/approvers` body `{"user_ids": [...]}`; `POST /changes/{id}/submit`, `/approve` (body `{comment?}`), `/request-changes` (body `{comment}`), `/revisions/{rid}/release-file` multipart `file`, `/release` body `{cutin_date: "YYYY-MM-DD"}`, `/comments` body `{body}` 201. `google_sub` for approvals comes from `request.state.google_sub`. The upload route reads the body with `await file.read()` and passes bytes; it declares `MAX_UPLOAD_BYTES` in the OpenAPI description. Storage comes from `clients.storage.from_env()` via a dependency `get_storage` so tests override it with `LocalStorage(tmp_path)`.

- [ ] **Step 1: Write failing tests** driving the API end to end with `as_user`: `test_initial_release_via_api` (same path as the lifecycle flow test, through HTTP, asserts `ChangeDetail.waiting_on` empties and `status` moves); `test_upload_renamed_exe_as_pdf_415` (bytes `b"MZ..."` with filename `x.pdf` and header `application/pdf` → 415, and `GET /changes/{id}` shows zero revisions — Review Focus 1); `test_upload_over_cap_413` (monkeypatch `MAX_UPLOAD_BYTES` to 10); `test_approver_state_fields` (`pending` → `signed`, `changes_requested` after request-changes); `test_release_requires_cutin_422`.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat: changes router`.

### Task 14: Documents, download and audit routers

**Files:**
- Create: `api/routers/documents.py`, `api/routers/audit.py`
- Test: `tests/test_api_documents.py`

**Interfaces:**
- Produces: `GET /documents?q=` → `list[DocumentSummary]` via `search_documents`; `GET /documents/{id}` → `DocumentDetail` via `document_detail`, 404 when missing; `GET /revisions/{id}/download` → 302 `Location: <signed_url(key, original_filename)>` and event `revision.downloaded` with `detail={"change_id": ...}`; `GET /revisions/{id}/download?which=redline` serves `redline_gcs_key` (404 when none). `GET /audit?entity_type=&entity_id=` → `list[EventOut]` (both params required, 422 otherwise).

- [ ] **Step 1: Write failing tests:** `test_search_endpoint_finds_released_text`, `test_download_redirects_and_logs_event` (TestClient `follow_redirects=False`, `Location` startswith `file://`, an event row `revision.downloaded` exists), `test_download_redline_404_when_absent`, `test_audit_requires_both_params`.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat: documents, download and audit routers`.

### Task 15: API container, local scripts, deploy workflow

**Files:**
- Create: `Dockerfile`, `.dockerignore`, `scripts/fetch-env.sh`, `scripts/test-api-local.py`, `.github/workflows/deploy-api.yml`
- Modify: `README.md`

**Interfaces:**
- Produces: `Dockerfile` copied from `~/src/tasks/Dockerfile` (one `requirements.txt`, no `api/requirements.txt`). `scripts/fetch-env.sh` writes `.env` from Secret Manager in project `$CHANGECTL_PROJECT` (secrets named in spec §13) plus `terraform/terraform.tfvars` values, like `~/src/tasks/scripts/fetch-env.sh`. `scripts/test-api-local.py` hits `/health`, `/me`, creates a change, uploads a generated xlsx, lists it; `--base-url` (default `http://localhost:8080`), `--token` (ID token; omitted → relies on dev bypass). `deploy-api.yml` from `~/src/tasks/.github/workflows/deploy-api.yml`: image `us-central1-docker.pkg.dev/${{ vars.CHANGECTL_PROJECT }}/changectl/changectl-api:latest`, service `changectl-api`, project from repo variable `CHANGECTL_PROJECT`, path filters `api/** clients/** repo/** services/** models/** Dockerfile requirements.txt`; smoke step curls `/health` on the service URL (public, no token).

- [ ] **Step 1: Build and run locally:** `docker build -t changectl-api . && docker run --rm -p 8080:8080 --env-file .env.local changectl-api` (an `.env.local` pointing at the compose Postgres on `host.docker.internal:5434`, `CHANGECTL_DEV_USER_EMAIL` set to a seeded test user, `CHANGECTL_LOCAL_STORAGE=/tmp/s`). Expected: `curl localhost:8080/health` → `{"status":"ok"}`.
- [ ] **Step 2: Run** `python scripts/test-api-local.py`. Expected: prints the created change number and the document listing, exit 0.
- [ ] **Step 3: README** sections: one-liner, how it works, local dev (compose, migrate, uvicorn, dev bypass), deployment, first-time setup pointer to `scripts/bootstrap-project.sh` (Task 16).
- [ ] **Step 4: Commit** `chore: API container, local scripts, deploy workflow`.

## Phase 4 — Infrastructure

### Task 16: Project bootstrap script and Terraform

**Files:**
- Create: `scripts/bootstrap-project.sh`, `terraform/versions.tf`, `terraform/variables.tf`, `terraform/cloudsql.tf`, `terraform/storage.tf`, `terraform/secrets.tf`, `terraform/iam.tf`, `terraform/api.tf`, `terraform/web.tf`, `terraform/domains.tf`, `terraform/outputs.tf`, `terraform/terraform.tfvars.example`
- Modify (separate repo, separate PR): `~/src/infra/cloudflare/main.tf`

**Interfaces:**
- Produces `scripts/bootstrap-project.sh` (idempotent, `set -euo pipefail`, takes `PROJECT_ID` and `BILLING_ACCOUNT` env): `gcloud projects create`, `gcloud billing projects link`, `gcloud services enable run.googleapis.com sqladmin.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com storage.googleapis.com iamcredentials.googleapis.com compute.googleapis.com`, `gcloud storage buckets create gs://${PROJECT_ID}-tf-state --location=us-central1 --uniform-bucket-level-access` with versioning, then **prints** the by-hand steps it cannot do: OAuth consent screen (app name `changectl`, external, in production, scopes openid/email/profile), OAuth web client with redirect `https://changectl.drolet.ai/api/auth/callback/google` and `http://localhost:3000/api/auth/callback/google`, Search Console verification of `drolet.ai` for this project, and `gcloud secrets versions add` commands for `changectl-google-oauth-client` (the client **secret** string only; the client id is the Terraform variable `google_oauth_client_id`), `changectl-auth-secret` (`openssl rand -base64 32`), the two Grafana secrets.
- Produces Terraform matching spec §13 verbatim; variables `project_id`, `region = "us-central1"`, `deployer_service_account` (email of the existing bens-project deployer), `google_oauth_client_id`, `web_hostname = "changectl.drolet.ai"`, `api_hostname = "api.changectl.drolet.ai"`, `db_tier = "db-f1-micro"`, `app_db_password` (sensitive), `owner_db_password` (sensitive). Backend `gcs`, bucket `${project_id}-tf-state` supplied via `-backend-config`, prefix `changectl`. Cloud Run services: `changectl-api` (image `.../changectl/changectl-api:latest`, SA `changectl-api`, Cloud SQL volume, env `CLOUD_SQL_CONNECTION_NAME POSTGRES_DB POSTGRES_USER=changectl_app POSTGRES_PASSWORD(secret) CHANGECTL_BUCKET GOOGLE_OAUTH_CLIENT_ID OTEL_*(secrets)`, `min 0 max 2`, `allUsers` invoker) and `changectl-web` (image `.../changectl/changectl-web:latest`, env `API_URL=https://api.changectl.drolet.ai AUTH_URL=https://changectl.drolet.ai AUTH_SECRET(secret changectl-auth-secret) AUTH_GOOGLE_ID=var.google_oauth_client_id AUTH_GOOGLE_SECRET(secret changectl-google-oauth-client) AUTH_TRUST_HOST=true`, `min 0 max 2`, `allUsers`). `google_cloud_run_domain_mapping` for both hostnames. `iam.tf` grants `deployer_service_account` `roles/run.admin`, `roles/artifactregistry.writer`, `roles/iam.serviceAccountUser` on both runtime SAs; grants `changectl-api` SA `roles/cloudsql.client`, `roles/storage.objectAdmin` on the bucket, `roles/secretmanager.secretAccessor` per secret, `roles/iam.serviceAccountTokenCreator` on itself. `secrets.tf` creates the five secrets (no versions for the by-hand ones; `changectl-db-password` versions from the variables). `outputs.tf`: both service URLs, both `rrdata` values the domain mappings expect.
- Produces in infra: two `cloudflare_record` CNAMEs `changectl` and `api.changectl` → `ghs.googlehosted.com`, `proxied = false`, `ttl = 60`, in `~/src/infra/cloudflare/main.tf` next to the consulting records.

- [ ] **Step 1: Write the Terraform** and `terraform.tfvars.example` with `c_...`-style placeholders only.
- [ ] **Step 2: Validate:** `cd terraform && terraform init -backend=false && terraform validate && terraform fmt -check`. Expected: Success.
- [ ] **Step 3: Commit** `feat: terraform for the dedicated project` in changectl; open a PR in `~/src/infra` titled `Add changectl DNS records` with the two CNAMEs (do not merge; Ben merges after the domain mappings exist).
- [ ] **Step 4 (Ben, by hand, outside this plan's gate):** run `scripts/bootstrap-project.sh`, the printed console steps, then `/terraform-plan` and `/terraform-apply` from this repo, then `scripts/migrate_db.py` against the new instance (via Cloud SQL Auth Proxy), then set GitHub repo variable `CHANGECTL_PROJECT`. The plan's remaining tasks do not depend on the apply having happened.

## Phase 5 — Web

### Task 17: Next.js scaffold, Auth.js, API client, sign-in

**Files:**
- Create: `web/` via `npx create-next-app@latest web --ts --app --tailwind --eslint --src-dir=false --import-alias "@/*"`, then `web/auth.ts`, `web/middleware.ts`, `web/lib/api.ts`, `web/lib/types.ts`, `web/app/api/auth/[...nextauth]/route.ts`, `web/app/signin/page.tsx`, `web/app/not-invited/page.tsx`, `web/app/layout.tsx` (nav: Changes, Documents, Users for doc managers, user name + sign out), `web/Dockerfile`, `web/.dockerignore`, `web/next.config.ts` (`output: "standalone"`), `web/.env.example`
- Test: `web/lib/api.test.ts` with vitest (add `vitest` dev dependency and `"test": "vitest run"`)

**Interfaces:**
- Produces (`web/auth.ts`): Auth.js v5 (`next-auth@beta`) with `Google` provider, `session: { strategy: "jwt", maxAge: 8 * 60 * 60 }`; `jwt` callback stores `account.id_token`, `account.refresh_token`, `account.expires_at`, and refreshes the ID token via Google's token endpoint when `expires_at` has passed; `signIn` callback calls `GET ${API_URL}/me` with the ID token and returns `"/not-invited"` on 403, `true` on 200; `session` callback exposes `session.user.role`, `session.user.isDocManager`, `session.user.id` from the `/me` response cached in the token.
- Produces (`web/lib/api.ts`): `apiFetch<T>(path: string, init?: RequestInit & { raw?: boolean }): Promise<T>` server-only (`import "server-only"`), reads the session via `auth()`, sets `Authorization: Bearer <id_token>`, throws `ApiError { status: number; detail: string; message?: string; changes?: string[] }` on non-2xx (parsing the API's `{detail, message}` body); for multipart, callers pass a `FormData` body and `apiFetch` leaves `Content-Type` unset. `web/lib/types.ts` mirrors `api/schemas.py` names exactly (`UserOut`, `ChangeSummary`, `ChangeDetail`, `RevisionOut`, `DocumentSummary`, `DocumentDetail`, `EventOut`).
- Produces (`web/middleware.ts`): everything except `/signin`, `/not-invited`, `/api/auth/*`, `/_next/*`, `/favicon.ico` requires a session; unauthenticated → redirect `/signin`.
- Produces: `web/Dockerfile` from `~/src/dp-website/Dockerfile` trimmed of the `APP_ENV/GIT_*` args, `node:22-alpine` runner, `PORT=8080`.

- [ ] **Step 1: Scaffold and configure** per the Files list; `npm i next-auth@beta`; `npm i -D vitest`.
- [ ] **Step 2: Write failing test** `web/lib/api.test.ts::maps 403 body to ApiError` — mock `fetch` returning `403 {"detail":"not_invited"}`; `await expect(apiFetch("/me")).rejects.toMatchObject({ status: 403, detail: "not_invited" })` (mock `auth()` via `vi.mock("@/auth")`).
- [ ] **Step 3: Run** `npm test` → FAIL. **Step 4: Implement** `lib/api.ts`. **Step 5: Run** → PASS.
- [ ] **Step 6: Verify sign-in locally** against the API with dev bypass off: `npm run dev` with `.env.local` (`AUTH_SECRET`, `AUTH_GOOGLE_ID`, `AUTH_GOOGLE_SECRET`, `API_URL=http://localhost:8080`, `AUTH_URL=http://localhost:3000`); API started with `GOOGLE_OAUTH_CLIENT_ID` set and a `users` row for Ben's email. Expected: Google sign-in lands on `/`; a second Google account not in `users` lands on `/not-invited`.
- [ ] **Step 7: Run** `npm run lint && npm run build`. Expected: clean.
- [ ] **Step 8: Commit** `feat(web): scaffold, Google sign-in, API client`.

### Task 18: Changes list and change detail (read side)

**Files:**
- Create: `web/app/page.tsx` (redirect to `/changes`), `web/app/changes/page.tsx`, `web/app/changes/[id]/page.tsx`, `web/components/StatusPill.tsx`, `web/components/ChangeTable.tsx`, `web/components/ApproverList.tsx`, `web/components/RevisionList.tsx`, `web/components/HistoryPanel.tsx`, `web/components/CommentList.tsx`, `web/lib/format.ts`

**Interfaces:**
- Consumes: `apiFetch`, `ChangeSummary`, `ChangeDetail`.
- Produces: `/changes?status=` with tabs All / Initiate / Approval / Implementation / Closed (default All, open statuses first); columns per spec §10.2; row click → `/changes/[id]`. Detail page renders the sections in spec §10.3 with the action bar left empty (Task 19 fills it). `lib/format.ts`: `relativeAge(iso: string): string` (`"3d"`, `"2h"`, `"just now"`), `bytes(n: number): string` (`"1.2 MB"`), `dateOnly(iso: string): string` (`YYYY-MM-DD`). `RevisionList` shows filename, `bytes`, a Download link to `/api/download/[revisionId]` (a Next route handler added here that calls the API download route with the token and relays the 302), and a `redline` badge when `redline_gcs_key` is set.

- [ ] **Step 1: Write failing test** `web/lib/format.test.ts`: `relativeAge` for 90 s → `"1m"`, 3 days → `"3d"`; `bytes(1258291)` → `"1.2 MB"`.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement** `format.ts`, the pages and components (server components; data fetched per request, `export const dynamic = "force-dynamic"`). **Step 4: Run** → PASS.
- [ ] **Step 5: Verify in the browser** against a local API with one seeded change: list shows it, detail shows fields, approvers as `pending`, history lists `change.created`.
- [ ] **Step 6: Run** `npm run lint && npm run build`; **Step 7: Commit** `feat(web): changes list and detail`.

### Task 19: Create / edit change, uploads, approvers, actions

**Files:**
- Create: `web/app/changes/new/page.tsx`, `web/app/changes/[id]/edit/page.tsx`, `web/components/ChangeForm.tsx`, `web/components/FileDrop.tsx`, `web/components/ApproverPicker.tsx`, `web/components/ActionBar.tsx`, `web/components/ConfirmSign.tsx`, `web/app/changes/actions.ts` (server actions)
- Modify: `web/app/changes/[id]/page.tsx` (mount `ActionBar`)

**Interfaces:**
- Produces server actions in `web/app/changes/actions.ts`, each returning `{ ok: true } | { ok: false; error: string }` and calling `revalidatePath`: `createChange(form: FormData)`, `updateChange(id, form)`, `attachRevision(id, form)` (fields `file`, `document_id` or `title`; client-side guard: accept only `.pdf,.docx,.xlsx`, reject > 25 MB with the message `"Files must be 25 MB or smaller"`), `removeRevision(id, rid)`, `setApprovers(id, userIds: string[])`, `submitChange(id)`, `approveChange(id, comment?)`, `requestChanges(id, comment)`, `addComment(id, body)`.
- Produces `ActionBar` rendering per status and viewer (spec §8): initiate + creator → Edit, Submit; approval + named approver who has not signed → Approve, Request changes; approval + anyone → Comment; implementation + doc manager → Release (wired in Task 20); closed → Comment only. `ConfirmSign` modal copy, verbatim: title `Sign approval`, body `You are signing as {name} ({email}). This records your approval of {CHG-number} "{title}" with the attached files as they are now.`, button `Approve`. `ApproverPicker` lists active users excluding the viewer, shows role next to each name.
- API error surfaces: `ApiError.detail` mapped to copy in `web/lib/errors.ts::describe(detail: string): string` for every lifecycle code (e.g. `self_approval` → `"You can't approve your own change."`, `document_busy` → `"That document already has a revision in an open change."`).

- [ ] **Step 1: Write failing test** `web/lib/errors.test.ts`: every code listed in Task 8's Interfaces has a non-empty, non-code string; unknown code → `"Something went wrong."`.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS.
- [ ] **Step 5: Verify in the browser:** create a change, drop an xlsx with a title, pick two approvers, submit; sign in as an approver (second Google account) and approve via the modal; request changes with a comment and watch the change reopen with approvals voided in History.
- [ ] **Step 6:** `npm run lint && npm run build`; **Step 7: Commit** `feat(web): change editing, uploads, approvals`.

### Task 20: Release modal, documents search, document detail

**Files:**
- Create: `web/components/ReleaseModal.tsx`, `web/app/documents/page.tsx`, `web/app/documents/[id]/page.tsx`, `web/components/SearchBox.tsx`
- Modify: `web/app/changes/actions.ts` (add `replaceReleaseFile(id, rid, form)`, `releaseChange(id, cutinDate)`), `web/components/ActionBar.tsx`

**Interfaces:**
- Produces `ReleaseModal` per spec §10: one row per attached revision showing the signed filename and an optional `Replace with clean file` input (same type as the signed file, enforced by `accept`), a `Cut-in date` input defaulting to today (local date), button `Release Rev {n}` where `n` comes from a new API field `next_revision_number` on `RevisionOut` (add to `api/schemas.py` and `ChangeDetail` assembly in Task 13's router — small modify, same commit). `/documents?q=` renders `SearchBox` (GET form, `q` in the URL) and the results columns from spec §10.5; `/documents/[id]` per §10.6 with each revision's change link and approvers.

- [ ] **Step 1: Verify in the browser:** release the approved change from Task 19 with today's cut-in; `/documents` lists the document with Rev 1; search for a word inside the xlsx finds it; a second change on the same document released → document detail shows Rev 2 current and Rev 1 superseded.
- [ ] **Step 2:** `npm run lint && npm run build && npm test`; `pytest -q` (for the schema change). **Step 3: Commit** `feat(web): release flow, documents and search`.

### Task 21: Users page and web deploy workflow

**Files:**
- Create: `web/app/users/page.tsx`, `web/components/InviteForm.tsx`, `web/app/users/actions.ts`, `.github/workflows/deploy-web.yml`

**Interfaces:**
- Produces `/users` (doc managers only; others get the API's 403 rendered as `Only doc managers can manage users.`): table name / email / role / doc manager / status; inline role select and doc-manager toggle; Deactivate button; `InviteForm` fields email, name, role, doc manager checkbox. The 409 `pending_approver` response renders `Finish or reassign {CHG-...} before deactivating {name}.` `deploy-web.yml` mirrors `deploy-api.yml` with `working-directory: web`, image `changectl-web`, service `changectl-web`, path filter `web/**`.
- [ ] **Step 1: Verify in the browser:** invite a second email, change its role, attempt to deactivate a pending approver and see the 409 copy.
- [ ] **Step 2:** `npm run lint && npm run build`; **Step 3: Commit** `feat(web): users page; web deploy workflow`.

## Phase 6 — Demo seed and hand-off

### Task 22: Demo seed, demo script, docs

**Files:**
- Create: `scripts/seed_demo.py`, `scripts/demo_files.py`, `docs/demo-script.md`
- Modify: `README.md`, `docs/hours.md`

**Interfaces:**
- Produces `scripts/demo_files.py`: `bom_xlsx(version: int) -> bytes` (sheet `BOM` with header `Item, Material No, Description, Supplier, Qty` and 8 rows; version 2 swaps row J4's connector supplier and adds a `Changes` sheet describing it), `cable_spec_docx() -> bytes`, `connector_spec_pdf() -> bytes` (pymupdf one page of text). `scripts/seed_demo.py` reads `SEED_TESA_EMAIL`, `SEED_BEN_EMAIL`, optional `SEED_SECOND_EMAIL` from env (never defaults to a real address; exits 2 if the first two are missing), then idempotently (keyed on change titles) creates the state in spec §14 by calling `services.lifecycle` functions with the seeded users as actors, writing persona approvals through `repo.changes.insert_approval` with `google_sub = "seed:<name>"`. Storage via `clients.storage.from_env()`. Prints the resulting change numbers.
- Produces `docs/demo-script.md`: the eight-step walkthrough from requirements §7 with the exact screens and clicks, plus a pre-demo checklist (second account invited, both accounts signed in once, seed run, `/documents` shows three documents).

- [ ] **Step 1: Write failing test** `tests/test_seed_demo.py::test_seed_is_idempotent` — run `seed_demo.main()` twice against `db_conn` with `LocalStorage(tmp_path)` and fake emails from env; expect 3 released documents, 4 changes, and identical counts after the second run.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS.
- [ ] **Step 5: README** adds "Demo" (seed command, demo-script link) and "Compliance posture" (one paragraph from spec §3, no claim of compliance). **Step 6: `docs/hours.md`** gets a row per build day.
- [ ] **Step 7: Commit** `feat: demo seed and script`.

---

## Self-review notes

- Spec coverage: §7 schema → Task 2; §8 lifecycle → Task 8; §9 routes → Tasks 11–14; §10 screens 1–7 → Tasks 17–21; §11 search → Task 9; §12 auth → Tasks 10, 17; §13 infra → Task 16; §14 seed → Task 22; §15 builder items left open deliberately; §16 resolutions embedded (dedicated project in Task 16, second account in Tasks 19/22, branding in Tasks 16/17).
- Review Focus 1–5 each have a named test in Tasks 13, 12, 8, 9, 8.
- Names used across tasks: `get_conn_dep`, `get_storage`, `LifecycleError`, `MAX_UPLOAD_BYTES`, `object_key`, `display_number`, `search_documents`, `document_detail`, schema model names mirrored in `web/lib/types.ts`.
