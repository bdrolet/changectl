# changectl — change-control MVP for pre-clearance startups

Design for the one-week case-study prototype built with Tesa Dinio Abad.
Requirements source: `~/src/consulting/docs/case-studies/tesa/requirements.md`
(extracted from the 2026-06-08 call; transcript alongside it). This document
decides how the thing gets made. Where it restates a requirement it cites
the FR/NFR number from that file.

## 1. Intent

A small med-tech or biotech startup needs to show investors, acquirers and
eventually the FDA that it tracked changes to its controlled documents with
rigor: who proposed a change, why, who approved it, and when the new
revision went live. Today they do it with a Word form and signatures, or not
at all. Enterprise tools (Siemens Teamcenter, SAP) are out of reach.

changectl is a deliberately plain web app: upload a document, open a change
against it, collect electronic approvals, release the revision, keep every
revision and every action forever, and search across all of it. The pitch to
a founder is "a folder system that an auditor will respect".

**Why now.** Tesa has startups from a panel who asked to be told when such a
tool exists. The prototype exists to be demoed to one of them. It is also the
first of two unpaid case studies for Ben's consulting practice, so the build
itself is part of the deliverable: hours and outcomes feed a write-up.

**Done** when Tesa has demoed it to one prospective client.

## 2. Goals, non-goals, anti-goals

**Goals**
- A founder watching the demo believes this would satisfy "do you have
  change control?" in diligence.
- Tesa can run the demo alone, signed in as herself, with seeded personas
  for the other roles.
- The full lifecycle works end to end on real files: initial release, then a
  revision, then search finds the current revision with its history.
- Every action is in an append-only audit trail with identity and timestamp.
- Buildable in one week by one person, deployable from a push to main.

**Non-goals (MVP, explicitly deferred by Tesa)**
- Material numbers as records, document numbering schemes, folders or
  multiple projects, custom roles, in-app viewers, automated redline
  acceptance, enterprise export. See requirements §5.
- Multi-tenancy. One workspace is one company. Portability to another GCP
  project is the hand-over story, not tenancy.
- Billing, pricing, marketing pages.

**Anti-goals (would make it a failure even if it worked)**
- Enforcing approval rules Tesa said must stay loose: one-per-role,
  mandatory Quality approver, fixed approver groups (FR-12).
- A UI that needs training. If a step needs a tooltip to explain, it is
  wrong.
- Anything that lets a record be edited or deleted after approval. The audit
  trail is the product.

## 3. Constraints

- **Time.** Hard cap of one week of build. Ben estimated three solid days of
  core work on the call; the rest is auth, infra, polish and the demo seed.
- **Cost.** Ben is between jobs. Everything scales to zero except the Cloud
  SQL instance, which is the one standing cost (`db-f1-micro`, roughly ten
  dollars a month plus a few GB of storage). Call this out to Ben before the
  first apply; it is a conscious spend.
- **Portability.** Ben's decision: a **dedicated GCP project** holding
  everything changectl needs: its own Cloud SQL instance, secrets, bucket,
  OAuth consent screen and client, Terraform state bucket. Nothing references
  `bens-project-462804` except the deploy identity (below). Hand-over to Tesa
  or a client is a project transfer. Chosen over the shared project because a
  GCP project has exactly one OAuth consent screen, and the shared one
  already carries Drive, Calendar and Contacts scopes for other services.
- **Domain.** Ben's decision: under `drolet.ai`, the consulting domain. DNS is
  the Cloudflare zone managed in `~/src/infra/cloudflare/main.tf`.
- **Stack.** Ben's decisions: Next.js frontend talking to a FastAPI backend;
  Google sign-in with an allowlist.
- **Compliance posture.** 21 CFR Part 11 is the frame (NFR-1). The MVP
  demonstrates the controls that matter in a demo: unique user identity,
  electronic signatures bound to the record, an immutable audit trail,
  revision history. It does **not** claim validation, and the UI must not
  say "Part 11 compliant". The write-up can describe the posture honestly.

## 4. Decisions Ben made

| Decision | Choice |
|---|---|
| UI | Next.js frontend, separate from the API |
| API | Python 3.13 FastAPI, the inbox/tasks service shape |
| Sign-in | Google sign-in, allowlisted emails only |
| Hosting | A new dedicated GCP project, own Cloud SQL instance, everything self-contained |
| Domain | `*.drolet.ai`: `changectl.drolet.ai` and `api.changectl.drolet.ai` |
| Name | `changectl`, also the app name on the Google sign-in screen |
| Live demo | Tesa submits and releases as herself; a second account she brings (a colleague's or her own second one) approves. No "act as" switch. |

## 5. Decisions made here (the builder's calls, flagged for Ben)

| Decision | Choice | Why |
|---|---|---|
| Frontend hosting | Cloud Run container (Next.js standalone output), not Cloudflare Pages/OpenNext | Ben asked for self-contained and portable. The consulting site's OpenNext path pins the frontend to Cloudflare; a container in the same project moves with everything else. dp-website already proves Next.js on Cloud Run. |
| Project bootstrap | Created once by hand with `gcloud`: project, billing link, APIs (Run, SQL Admin, Artifact Registry, Secret Manager, Storage, IAM Credentials), a Terraform state bucket in the new project, OAuth consent screen + web client, Search Console verification of `drolet.ai` for the new project. Terraform owns everything after that. A `scripts/bootstrap-project.sh` records the exact commands. | Terraform cannot create a project's OAuth client or consent screen, and a state bucket has to exist before `init`. |
| Deploy identity | The existing deployer service account from `bens-project-462804` (behind the `bdrolet`-scoped WIF provider) is granted `run.admin`, `artifactregistry.writer` and `iam.serviceAccountUser` **in the new project**. | Reuses the GitHub secrets every repo already has. On hand-over the new owner swaps in their own deployer; it is one IAM binding and two repo secrets. |
| Hostnames | `changectl.drolet.ai` (frontend), `api.changectl.drolet.ai` (API) | Cloud Run domain mappings, Cloudflare CNAME to `ghs.googlehosted.com` unproxied, exactly like `tasks-api.drolet.cloud`. |
| Auth plumbing | Auth.js (next-auth v5) in Next.js with the Google provider. The Next.js server forwards the user's Google **ID token** on every API call. FastAPI verifies it against Google's certificates with `google-auth`, checks the audience is our OAuth client id, then looks the email up in `users`. | No shared secret to rotate, no second identity system. Allowlist enforcement lives in one place (the API), so a direct API call is no more privileged than the UI. |
| Allowlist | The `users` table **is** the allowlist. A Google account whose email is not in `users` gets "ask your doc manager to invite you". Doc managers invite by email and set role. | Tesa needs to add a founder without Ben. |
| Browser → API path | Browser never calls the API directly. Next.js route handlers and server components proxy it. | One CORS-free origin, token never reaches the browser's JS. |
| File storage | One GCS bucket, object key `documents/{document_id}/{revision_id}/{original_filename}`, uniform bucket-level access, no public access, versioning on. Downloads are short-lived signed URLs minted by the API. | Drive is Ben's personal store (docs service); a bucket is portable. Signed URLs keep file bytes off the API's hot path. |
| Search | Postgres `tsvector` generated column over document name + extracted text of the **current released revision**, plus a trigram index on names. Extraction: `pymupdf` for PDF (as in docs), `python-docx` for Word, `openpyxl` for Excel cell text. | Proven in the docs service. No Vertex, no Elasticsearch. |
| Rejection | An approver can **request changes**. The change returns to Initiate with a required comment; prior approvals are voided and recorded as voided. | Tesa never described rejection, but a demo without it looks naive. Minimal, auditable. |
| Multi-document changes | One change can carry **one or more** document revisions (FR-7). Released together. | The initial-release example on the call submitted a BOM plus a describing sheet. |
| Roles per user | Exactly one of Engineering, Operations, Quality, Other, plus an independent `is_doc_manager` flag. | Matches "usually one role" and "doc manager is also an engineer in a startup" (FR-18, FR-19). Roles are display-only. |
| Who can do what | Any user: upload, create a change, submit, comment, approve when named. Doc manager additionally: release, invite users, change a user's role. Nobody: edit or delete a submitted change, delete a document or revision, approve their own change. | FR-11, anti-goals. |
| Revision numbering | Integer per document, assigned at **release**. Draft revisions attached to an open change show as "Rev N (pending)". | Avoids gaps when a change is abandoned. |
| Release file | By default the file the approvers signed **is** the released file. The doc manager may optionally upload a clean replacement (redlines accepted offline) at release; then the signed upload is kept as the revision's redline, and the release event records both hashes. | An initial release has nothing to accept, and forcing a re-upload there is friction. Keeping the signed bytes means every approval hash still matches a stored file. |
| Upload cap | 25 MB per file. | Uploads cross two Cloud Run hops, each limited to 32 MiB per request. BOMs and spec sheets are far smaller. Raising it later means browser-direct uploads to GCS, not a config change. |
| DB roles | Two: `changectl_owner` for migrations, `changectl_app` for Cloud Run with INSERT-only on `events`. | With one role the append-only grant is hollow. |
| Search columns | One `tsvector` per table (`documents.title`, `revisions.extracted_text`), ranked as a sum. | A generated column cannot span tables. |
| Concurrent changes | A document with a revision pending in an open change cannot be attached to a second open change. | Two redlines of the same revision would race at release. |
| Personal data in the repo | Tesa's and the personas' emails enter the seed from tfvars/env, never a committed file. | The repo is public. |
| Audit trail | A single `events` table, append-only (INSERT-only grant for the API role, no UPDATE/DELETE), one row per action with actor, timestamp, entity, action, JSON detail. The UI's history views read it. | Part 11 posture with one table. |
| Electronic signature | Approving = a row in `approvals` with the approver's user id, the Google `sub`, email, UTC timestamp, the SHA-256 of the file(s) at that moment, and a required "meaning of signature" line fixed to "Approved". The UI re-confirms with a click-through that names the user and the change. | Signature bound to the record contents, not just the record id. No password re-entry in MVP; noted as a Part 11 gap. |
| Observability | OTel to Grafana Cloud, metrics prefixed `changectl_`, copied from tasks. | Same as every service. |
| Repo | `~/src/changectl`, GitHub `bdrolet/changectl`, public like tasks. | Case study artefact; nothing personal in it. |

## 6. Architecture

```
Browser ──HTTPS──▶ changectl.drolet.ai   (Cloud Run: Next.js 16, Auth.js, Tailwind 4)
                        │  server-side fetch, Authorization: Bearer <Google ID token>
                        ▼
                  api.changectl.drolet.ai (Cloud Run: FastAPI, python 3.13)
                        │                         │
                        ▼                         ▼
                  Cloud SQL Postgres 16       GCS bucket (files)
                  (own instance `changectl`)
```

Both Cloud Run services are public (`allUsers` invoker). Authentication is
the Google ID token, verified in the API. The frontend holds no database
credentials.

### Repo layout

```
changectl/
  api/                FastAPI app: main.py, auth.py, errors.py, routers/
  clients/            otel.py, gcs.py, google_id_token.py
  repo/               schema.sql + one module per table group
  services/           lifecycle.py, extract.py, search.py, audit.py
  models/             pydantic types
  web/                Next.js app (app router), Dockerfile
  terraform/          cloudsql.tf, api.tf, web.tf, storage.tf, secrets.tf, oauth notes
  scripts/            migrate_db.py, seed_demo.py, fetch-env.sh, test-api-local.py
  docs/superpowers/   this spec, then the plan
  .github/workflows/  ci.yml, deploy-api.yml, deploy-web.yml
```

Layer rules are the tasks rules verbatim: `clients/` I/O only, `repo/` DB
only on an open connection, `services/` business logic with no HTTP,
`api/routers/` thin transport.

## 7. Domain model and schema

```sql
users        (id, email unique, name, google_sub nullable until first sign-in,
              role enum(engineering,operations,quality,other), is_doc_manager bool,
              invited_by, created_at, deactivated_at nullable)

documents    (id, title, created_by, created_at,
              current_revision_id nullable)            -- latest released

revisions    (id, document_id, revision_number nullable until released,
              change_id, original_filename, content_type, byte_size, sha256,
              gcs_key,                                   -- the released (or to-be-released) file
              redline_gcs_key nullable, redline_sha256 nullable,
                                                         -- set only when release replaced the signed file
              extracted_text, search tsvector generated from extracted_text,
              uploaded_by, uploaded_at,
              released_at nullable, released_by nullable,
              superseded_at nullable)

changes      (id, number serial shown as CHG-0001, title,
              description, reason, justification,
              status enum(initiate,approval,implementation,closed),
              created_by, created_at, submitted_at, approved_at,
              closed_at, cutin_date nullable)

change_revisions (change_id, revision_id)              -- documents in a change

approvers    (change_id, user_id, added_by, added_at)   -- the named set

approvals    (id, change_id, user_id, google_sub, email, decision enum(approved,changes_requested),
              comment, file_sha256s jsonb, signed_at, voided_at nullable, voided_reason)

comments     (id, change_id, user_id, body, created_at)

events       (id, at, actor_user_id, entity_type, entity_id, action, detail jsonb)
             -- INSERT-only for the application role
```

Integrity rules enforced in `services/lifecycle.py` and, where cheap, as DB
constraints:
- A change in `approval` or later cannot change its description, reason,
  justification, approver set or attached revisions. Edits in `initiate` are
  recorded as events.
- `approvals.user_id` must be in `approvers` for that change and must not
  equal `changes.created_by`.
- A change moves to `implementation` automatically when every approver has a
  non-voided `approved` row.
- Release requires `is_doc_manager` and a `cutin_date` (default today). For
  each attached revision the doc manager either keeps the signed file or
  uploads a clean replacement; a replacement moves the signed file to
  `redline_gcs_key`/`redline_sha256` and re-extracts text from the new one.
  Release assigns `revision_number`, sets `documents.current_revision_id`,
  stamps `superseded_at` on the prior current revision, writes a release
  event carrying both hashes, and closes the change.

## 8. Lifecycle (from requirements §3)

| Status | Allowed actions | Actor |
|---|---|---|
| **initiate** | edit fields, attach/replace/remove revisions (new files or a redlined upload against an existing document), add/remove approvers, submit | creator |
| **approval** | approve, request changes, comment | named approvers; anyone may comment |
| **implementation** | optionally replace a revision's file with the clean version, set cut-in date, release | doc manager |
| **closed** | view, download, comment | anyone |

Request changes → `initiate`, all approvals voided with reason
`changes_requested_by:{user}`, creator notified in-app (no email in MVP).

## 9. API surface (FastAPI, JSON, all under the ID-token guard)

```
GET  /me
GET  /users                     doc manager only for invite controls, otherwise list
POST /users                     doc manager: invite {email, name, role, is_doc_manager}
PATCH /users/{id}               doc manager: role, is_doc_manager, deactivate

GET  /documents?q=              search (FTS over current revision + trigram on title)
GET  /documents/{id}            document + revisions + their changes
GET  /revisions/{id}/download   302 to a signed URL (10 min), event logged

POST /changes                   create in initiate
GET  /changes?status=
GET  /changes/{id}              full record: fields, revisions, approvers, approvals, comments, events
PATCH /changes/{id}             initiate only
POST /changes/{id}/revisions    multipart upload: new document (title) or against document_id
DELETE /changes/{id}/revisions/{rid}   initiate only
PUT  /changes/{id}/approvers    initiate only, full set
POST /changes/{id}/submit
POST /changes/{id}/approve      {comment?}
POST /changes/{id}/request-changes {comment}
POST /changes/{id}/revisions/{rid}/release-file   multipart, implementation only, optional
POST /changes/{id}/release      {cutin_date}
POST /changes/{id}/comments

GET  /audit?entity_type=&entity_id=    events, newest first
GET  /health
```

Errors follow tasks' `api/errors.py` shape. Every mutating route writes an
`events` row in the same transaction.

## 10. UI (Next.js, app router, Tailwind 4)

Seven screens. Plain, dense, one accent colour. No dashboard widgets.

1. **Sign in.** Google button. Unknown email → explanatory page, no form.
2. **Changes list.** Default view after sign-in. Tabs by status. Columns:
   number, title, documents, created by, waiting on (approver names not yet
   signed), age. "New change" button.
3. **Change detail.** Header with number, title, status pill. Fields
   description / reason / justification. Documents section listing each
   revision with filename, size, download, and "redline" badge. Approvers
   section with each name and signed / pending / changes-requested state.
   Action bar matching the status table in §8. Comments and a full
   **History** (events) panel at the bottom.
4. **New / edit change.** Fields, file drop zone (PDF, DOCX, XLSX only, 25 MB
   cap), "attach to existing document" picker, approver multi-select
   (excluding yourself).
5. **Documents.** Search box, results with title, current revision, released
   date, releasing doc manager. Row opens:
6. **Document detail.** Current revision, download, every prior revision
   with its change number, who approved, cut-in date.
7. **Users.** Doc manager only. Table and an invite form.

The release step gets its own modal: for each revision in the change, the
signed file's name with an optional "replace with clean file" slot, then a
cut-in date defaulting to today, then "Release Rev N".

## 11. Search (FR-21, FR-22)

On every revision upload the API extracts text synchronously (files are
small; cap extraction at 2 MB of text) and stores it. The `search` tsvector
is generated from `title || extracted_text`. `GET /documents?q=` ranks with
`ts_rank` over **current released revisions only**, falling back to `ILIKE`
on title when the query has no lexemes. Results show the matched document's
current revision; prior revisions are reachable from the document page.

## 12. Auth in detail

- Google Cloud OAuth client (web application) created **by hand** in the
  console of the dedicated project; Terraform cannot create OAuth clients.
  Client id and secret go in Secret Manager (`changectl-google-oauth-client`).
  Consent screen: app name `changectl`, external, publishing status "In
  production" so any Google account can attempt sign-in (the allowlist does
  the gating). Scopes: `openid email profile` only, which need no Google
  verification and show no unverified-app warning.
- Next.js: Auth.js v5, Google provider, JWT session strategy, session max
  age 8 hours. The Google ID token is kept in the encrypted session cookie
  and refreshed with the refresh token when expired. `signIn` callback calls
  `GET /me`; a 403 blocks sign-in with the "not invited" page.
- API: `api/auth.py` verifies the bearer ID token with
  `google.oauth2.id_token.verify_oauth2_token`, requires `email_verified`,
  matches `aud` to our client id, then loads the `users` row by email. First
  successful sign-in stores `google_sub`; later tokens must match it.
- Deactivated users 403 everywhere; their past approvals remain.

## 13. Infrastructure (Terraform, state bucket in the dedicated project, prefix `changectl`)

- `cloudsql.tf`: `google_sql_database_instance` `changectl`, Postgres 16,
  `db-f1-micro`, 10 GB SSD, automated backups on, deletion protection on;
  database `changectl`, user `changectl` with a generated password in Secret
  Manager (`changectl-db-password`).
- `storage.tf`: bucket `changectl-files-<project>` with versioning, uniform
  access, no public access, 30-day soft-delete.
- `api.tf`: Artifact Registry repo `changectl`; service account
  `changectl-api` with `cloudsql.client`, `storage.objectAdmin` on the bucket
  only, `secretmanager.secretAccessor` on its secrets, and
  `iam.serviceAccountTokenCreator` on itself so it can sign download URLs
  without a key file; Cloud Run v2 service
  `changectl-api`, public invoker, min 0 max 2, Cloud SQL connector volume,
  env for DB, bucket, OAuth client id, OTel.
- `web.tf`: Cloud Run v2 service `changectl-web`, public invoker, min 0 max
  2, env `API_URL`, `AUTH_SECRET`, OAuth client id and secret from Secret
  Manager, `AUTH_URL=https://changectl.drolet.ai`.
- `secrets.tf`: all owned here — `changectl-db-password`,
  `changectl-google-oauth-client` (JSON: id + secret), `changectl-auth-secret`,
  `changectl-grafana-otlp-endpoint`, `changectl-grafana-otlp-token`. The
  Grafana values are copies of the shared ones, entered by hand once, so no
  cross-project secret reads exist.
- `iam.tf`: the cross-project bindings for the deployer service account
  (§5) and the OAuth client id as a plain variable.
- Domain mappings for both hostnames in Terraform; DNS records added to
  `~/src/infra/cloudflare/main.tf` as unproxied CNAMEs to
  `ghs.googlehosted.com` (separate PR in infra). Bootstrap step: the
  hosting project must have `drolet.ai` verified in Search Console before a
  mapping will apply.
- Deploys reuse the existing `GCP_WIF_PROVIDER` / `GCP_DEPLOYER_SA` GitHub
  secrets; the provider is scoped to the `bdrolet` owner, so no infra change.
- `deploy-api.yml` and `deploy-web.yml` mirror tasks' `deploy-api.yml`
  (WIF auth, build, push, `gcloud run deploy`, smoke `GET /health`). Paths
  filters split api and web.

## 14. Demo seed (`scripts/seed_demo.py`)

Idempotent. Creates the demo company's users and a worked history so the
screens are not empty when Tesa opens them:

- Users: Tesa (quality, doc manager), Ben (engineering, doc manager), and
  three personas, "Priya, engineering", "Marcus, operations", "Dana,
  quality". Personas exist only to populate the seeded history; their
  approval rows are written by the seed and they never sign in. The live
  demo's approver is the second account Tesa brings, invited through the
  Users screen before the demo.
- Documents: `Prototype BOM.xlsx` (Rev 1 released, CHG-0001 "Initial
  release of prototype BOM"), `Cable Assembly Spec.docx` (Rev 1 released),
  `Supplier Spec - Connector.pdf` (Rev 1 released).
- One open change in approval: CHG-0004 "Replace EOL connector J4", BOM
  redline attached, two approvers, one signed.

The live demo then does the revision flow by hand: Tesa requests changes or
approves, releases Rev 2, searches for the BOM, shows history. Scripted in
the requirements file §7.

## 15. Left to the builder

- Exact Tailwind styling, component library choice (none, or shadcn/ui).
- Whether to show PDF thumbnails. Default no (non-goal: in-app viewer).
- Extraction library edge cases (password-protected PDFs: store, mark
  `extracted_text` null, still searchable by title).
- Pagination thresholds. Default: none under 200 rows.
- CI: ruff + pytest for `api/`, `npm run lint && npm run build` for `web/`.
- Test strategy: services unit-tested against a real local Postgres via
  docker-compose (as finances does); one API smoke script against the
  deployed URL.

## 16. Resolved questions

Settled with Ben on 2026-10-19 after the builder check: dedicated GCP
project (§3, §5); Tesa brings the second account for live approvals (§4,
§14); `changectl` is the name on the sign-in screen and in the hostnames
(§4). Cut-in date defaults to today and is the single release-date field.
Tesa's email and the second account's email arrive via tfvars at seed time.

## 17. Hours

Track in `docs/hours.md` in this repo as the build proceeds (task says hours
and outcomes feed the case study). Design and transcription so far: logged
there at first commit.
