# changectl MVP test plan

A hand-off document: a fresh Claude Code session (or a person) should be able
to execute this plan end to end from this file alone, record results in the
table at the bottom, and report. Written 2026-10-21 after the first deploy.
Spec: `docs/superpowers/specs/2026-10-19-changectl-mvp-design.md`. Plan it
implements: `docs/superpowers/plans/2026-10-19-changectl-mvp.md`.

## 0. Ground truth for the executor

| Thing | Value |
|---|---|
| Repo | `~/src/changectl` (github `bdrolet/changectl`), main at or after `82abf05` |
| GCP project | `changectl-drolet` (dedicated; nothing shared with other projects except the deploy identity) |
| Web | https://changectl.drolet.ai (Cloud Run `changectl-web`, us-central1) |
| API | https://api.changectl.drolet.ai (Cloud Run `changectl-api`); `/health` is public, everything else needs a Google ID token |
| Database | Cloud SQL `changectl-drolet:us-central1:changectl`, db `changectl`, owner user `changectl`, app user `changectl_app`; passwords in `terraform/terraform.tfvars` (gitignored, on Ben's machine) |
| Files | GCS bucket `changectl-drolet-files` (versioned, 30-day soft delete) |
| Sign-in | Google OAuth client `changectl-web`. The consent screen is in **Testing** status: only test users listed on the Google Auth Platform → Audience page can sign in. `ben@drolet.cloud` is one. Testing-mode refresh tokens expire after 7 days. |
| App allowlist | the `users` table. `ben@drolet.cloud` is the first row (engineering, doc manager). A Google account not in `users` lands on `/not-invited`. |
| Local dev | `docker compose up -d` (Postgres 16 on `localhost:5434`, user/pass/db `changectl`); `.venv/bin/pytest -q` with `CHANGECTL_TEST_DSN=postgresql://changectl:changectl@localhost:5434/changectl`; web: `cd web && npm ci && npm run lint && npm run build && npm test` |
| API without Google locally | start uvicorn with `K_SERVICE` unset and `CHANGECTL_DEV_USER_EMAIL=<email in users>`; every request then acts as that user. Inert on Cloud Run. |
| DB access from a laptop | `cloud-sql-proxy changectl-drolet:us-central1:changectl --port 5435 &` then `POSTGRES_HOST=localhost POSTGRES_PORT=5435 POSTGRES_DB=changectl POSTGRES_USER=changectl POSTGRES_PASSWORD=<owner pw>`; `psql` is not installed on Ben's machine, use `.venv/bin/python -c` with psycopg or the repo scripts |
| Deploys | push to `main` → `.github/workflows/deploy-api.yml` / `deploy-web.yml` (path-filtered) via WIF as `inbox-deployer@bens-project-462804.iam.gserviceaccount.com`; repo variable `CHANGECTL_PROJECT=changectl-drolet` |
| Demo data | `scripts/seed_demo.py` (needs `SEED_TESA_EMAIL`, `SEED_BEN_EMAIL`, optional `SEED_SECOND_EMAIL`; idempotent by change title); `scripts/demo_files.py --out <dir>` writes the five demo files; `docs/demo-script.md` is the walkthrough |

Rules for the executor:

- Never commit a real email, password or secret. Example addresses are `*@example.test`; demo personas are `*@demo.example`.
- Never run two Python test suites at once: the fixtures drop and recreate the public schema of the shared local database.
- Production data is a demo, but treat it as such: do not delete rows by hand; re-seed instead (the seed is idempotent and a fresh database comes from `scripts/migrate_db.py`).
- Browser steps assume the Claude in Chrome tools or a human at a browser signed in as a test user. The Google consent click is the user's; ask before signing in as someone.
- Record every test as PASS / FAIL / BLOCKED / SKIP with a one-line note in §9. A FAIL needs the observed behaviour, not just "failed".

## 1. Scope

What this plan covers: the MVP as built (spec §4 to §14): sign-in and allowlist, the change lifecycle with electronic approvals, revisions and release, search, documents, downloads, audit trail, users management, infrastructure, deploy pipeline, and the demo path. Out of scope: load testing, 21 CFR Part 11 validation (the product does not claim it), browser matrix beyond current Chrome.

## 2. Automated suites (run first, both must be green)

| ID | Test | Command | Expected |
|---|---|---|---|
| A1 | Python unit + API tests | `docker compose up -d && CHANGECTL_TEST_DSN=postgresql://changectl:changectl@localhost:5434/changectl .venv/bin/pytest -q` | 110 passed (count may grow; 0 failed), one known OTel `LoggingHandler` DeprecationWarning |
| A2 | Lint, format, types | `.venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/mypy clients/ services/ repo/ models/ api/` | all clean |
| A3 | Web unit tests | `cd web && npm test` | 26 passed (count may grow) |
| A4 | Web lint + build | `cd web && npm run lint && npm run build` | clean, standalone output |
| A5 | Terraform | `cd terraform && terraform init -backend=false && terraform validate && terraform fmt -check -recursive` | valid, formatted |
| A6 | CI on GitHub | `gh run list --repo bdrolet/changectl --limit 5` | latest `CI` and `CI web` runs on main succeeded |
| A7 | Deploy workflows | same listing | latest `Deploy API` and `Deploy web` runs succeeded |

The Review Focus inputs the plan pinned with tests (verify they exist and pass as part of A1/A3): renamed `.exe` as PDF → 415 and no revision stored (`tests/test_api_changes.py`); deactivating a pending approver → 409 `pending_approver` with change numbers (`tests/test_api_users.py`); double approve idempotent including the final approver (`tests/test_lifecycle.py`); stopword-only search falls back to ILIKE (`tests/test_search.py`); replacement file of a different type → 409 `type_mismatch` (`tests/test_lifecycle.py`).

## 3. Infrastructure and deployment checks (read-only)

| ID | Check | How | Expected |
|---|---|---|---|
| I1 | API health | `curl -sS https://api.changectl.drolet.ai/health` | `{"status":"ok"}` |
| I2 | API rejects anonymous | `curl -sS -o /dev/null -w '%{http_code}' https://api.changectl.drolet.ai/me` | `401` |
| I3 | Web serves sign-in | `curl -sS -o /dev/null -w '%{http_code}' https://changectl.drolet.ai/signin` | `200` |
| I4 | Root redirects | `curl -sS -o /dev/null -w '%{http_code}' https://changectl.drolet.ai/` | `307` (to `/signin` when anonymous) |
| I5 | Protected pages redirect anonymous | same for `/changes`, `/documents`, `/users` | `307` each |
| I6 | TLS and DNS | `dig +short changectl.drolet.ai` and `api.changectl.drolet.ai` | CNAME `ghs.googlehosted.com.`; curl works without `-k` |
| I7 | Cloud Run config | `gcloud run services describe changectl-web --region us-central1 --project changectl-drolet --format=json` | env has `AUTH_URL=https://changectl.drolet.ai`, `AUTH_GOOGLE_ID` set to the real client id (ends `.apps.googleusercontent.com`, not `pending`), `AUTH_GOOGLE_SECRET` and `AUTH_SECRET` from secrets, `AUTH_TRUST_HOST=true`; `changectl-api` has `GOOGLE_OAUTH_CLIENT_ID` equal to the web's, `CHANGECTL_BUCKET=changectl-drolet-files`, `POSTGRES_USER=changectl_app`; both `allUsers` invoker; min instances 0, max 2 |
| I8 | Secrets present | `gcloud secrets list --project changectl-drolet` | five secrets; `changectl-google-oauth-client` has a version 2 (version 1 was a placeholder) |
| I9 | Bucket posture | `gcloud storage buckets describe gs://changectl-drolet-files --format=json` | uniform access, public access prevention enforced, versioning enabled, soft delete 30 days |
| I10 | Cloud SQL posture | `gcloud sql instances describe changectl --project changectl-drolet` | Postgres 16, Enterprise edition, `db-f1-micro`, backups enabled, deletion protection on, public IP with no authorized networks |
| I11 | Audit table is append-only | through the proxy as `changectl_app` (password = `app_db_password` in tfvars): `UPDATE events SET action='x' WHERE false` and `DELETE FROM events WHERE false` | both raise insufficient privilege; `INSERT`/`SELECT` allowed |
| I12 | Terraform drift | `cd terraform && terraform init -backend-config="bucket=changectl-drolet-tf-state" && terraform plan` | no changes (image differences are ignored by design) |
| I13 | Cost guard | `gcloud run services list --project changectl-drolet`, `gcloud sql instances list` | exactly two services and one instance; nothing else billable was created |

## 4. Sign-in and allowlist (browser)

Precondition: a Google account listed as a test user on the Audience page. `ben@drolet.cloud` is; others must be added there first (Google Auth Platform → Audience → Test users → Add users).

| ID | Steps | Expected |
|---|---|---|
| S1 | Open https://changectl.drolet.ai, click **Sign in with Google**, choose a test user that is in `users` | lands on `/changes`; nav shows Changes, Documents, the user's name and Sign out; **Users** appears only for doc managers |
| S2 | Sign in as a Google test user who is **not** in `users` (ask Ben which account to use; add it as a Google test user first) | lands on `/not-invited` with the heading "You're not on the list yet" and the address in the body; no session; `/changes` still redirects to `/signin` |
| S3 | Sign in as a Google account that is **not** a test user | Google itself refuses ("app is in testing"); nothing reaches the app. Document the Google message. |
| S4 | While signed in, open `/api/auth/session` in the browser | JSON contains name/email/role/isDocManager and **no** `idToken`, `id_token`, `access_token` or `refresh_token` fields |
| S5 | Sign out via the nav button | back on `/signin`; `/changes` redirects to `/signin` |
| S6 | Session survives a reload and a new tab | still signed in; the nav shows the same user |
| S7 | Token refresh (needs > 1 hour) | sign in, wait 65 minutes with the tab idle, reload `/changes` | page renders without a 401 error box (the server refreshes the Google token in memory for that request) |
| S8 | Deactivated user | as a doc manager deactivate a second test user who is not a pending approver (see §7), then have that person reload | they get `/not-invited` or a 403 message; their past approvals remain visible on changes |

## 5. Lifecycle, approvals and release (browser, two accounts)

Preconditions: two signed-in accounts in `users`: **A** (creator, engineering), **B** (approver, any role), and a doc manager **D** (can be A). The seeded personas (Priya, Marcus, Dana) cannot sign in. Files: run `.venv/bin/python scripts/demo_files.py --out ~/changectl-test` to get `Test Fixture Spec.docx`, `Prototype BOM.xlsx`, `Prototype BOM rev2.xlsx`, `Cable Assembly Spec.docx`, `Supplier Spec - Connector.pdf`. Use fresh titles (suffix the date) so re-runs do not collide with the seed.

| ID | Steps | Expected |
|---|---|---|
| L1 | As A: Changes → **New change**; fill Title, Description, Reason; click **Same as reason**; **Create change** | justification copied; redirected to the change detail page in status *initiate* with number `CHG-nnnn`; History shows `change.created` |
| L2 | As A: **Edit** → under Documents choose `Test Fixture Spec.docx`, leave "New document", title "Test Fixture Spec <date>", **Attach file** | revision listed as *pending* with filename and size; History (on detail) shows `revision.attached` |
| L3 | As A: attach a second file to the same change against an existing released document (pick one in the "Attach to existing document" select) | allowed; now two revisions |
| L4 | As A: try to attach a file to a document that already has a pending revision in another open change (the seeded Prototype BOM if the seed ran) | error line: "That document already has a revision in an open change." |
| L5 | As A: Approvers → tick B only, **Save approvers** | B listed as pending; A is not offered in the picker |
| L6 | As A: **Submit** with no approvers (new change) | error "no approvers" copy; status stays initiate |
| L7 | As A: **Submit** with approvers but no files (new change) | error "no revisions" copy |
| L8 | As A: Submit the L1 change | status *approval*; Edit/Submit gone; **Comment** available; Changes list shows "Waiting on: B" |
| L9 | As A (creator): open the change | no Approve button (A is not an approver); Comment works and appears with name and date |
| L10 | As B: **Approve** → dialog "Sign approval" with "You are signing as B (email). This records your approval of CHG-nnnn "title" with the attached files as they are now." → **Approve** | B shows *signed*; since B was the only approver the change moves to *implementation*; History shows `change.approved` and `change.approval_complete` |
| L11 | As B, before signing, on a change where B is one of two approvers: **Request changes** with an empty comment, then with only spaces (once B has signed, B gets neither Approve nor Request changes) | empty: the browser's required-field prompt; spaces: "Add a comment explaining what needs to change." |
| L12 | As B: **Request changes** with a comment on a change in approval | status back to *initiate*; B's row shows *changes requested* with the comment and time under it; prior approvals show *voided* with reason `changes_requested_by:<email>` in the approvals section; creator can Edit again |
| L13 | As A: resubmit the L12 change; as B approve | works (no unique-violation error); History shows the voided rows, then a fresh approval |
| L14 | As a non-doc-manager (B): open an *implementation* change | no **Release** button |
| L15 | As D: **Release** on the L10 change → dialog shows the signed filename, optional "Replace with clean file", **Cut-in date** defaulting to today → **Release Rev 1** | status *closed*; revision shows *Rev 1*; document now exists in Documents with Rev 1, released today by D; History shows `change.released` |
| L16 | As D: release with a replacement file of the **same** type (`Prototype BOM rev2.xlsx` against an xlsx revision) | released; revision shows a **Download redline** link (the originally signed file) and **Download** (the clean file) |
| L17 | As D: release with a replacement of a **different** type (a .pdf for an .xlsx revision) | the file input refuses it (accept filter) or the server answers "type mismatch" copy; nothing released |
| L18 | As D: try Release with the cut-in date cleared | **Release** is disabled; nothing released (the server's `cutin_required` copy, "Enter a cut-in date before releasing.", is only reachable without the UI) |
| L19 | Double-click **Approve** quickly as the final approver | one approval row, no error; status moves once |
| L20 | Double-click **Release** / re-run release on an already closed change | second attempt gets "wrong status" copy; revision numbers unchanged |
| L21 | Revision flow: new change by A attaching a redline against the L15 document, approver B, submit, B approves, D releases | document shows Rev 2 current and Rev 1 *superseded*; Documents search returns Rev 2 |
| L22 | Non-creator opens `/changes/<id>/edit` for A's draft | redirected to the detail page |
| L23 | Remove a revision from a draft; remove the last revision of a brand-new document | revision gone; the new document disappears from the "attach to existing" list |
| L24 | Comments on a closed change | allowed and listed |

## 6. Uploads, downloads and files

| ID | Steps | Expected |
|---|---|---|
| F1 | Attach a `.txt` or `.png` | the file input refuses (accept `.pdf,.docx,.xlsx`) |
| F2 | Rename a `.png` to `.pdf` and attach | server answers 415 → "not a supported file" copy; no revision listed |
| F3 | Attach a 26 MB file (e.g. `dd if=/dev/urandom bs=1m count=26 > big.pdf` renamed appropriately — it will also fail sniffing, so use a real large PDF if available) | client message "Files must be 25 MB or smaller" before upload, or server 413 copy |
| F4 | Attach a real 20 MB PDF | accepted (server-action body limit is 27 MB) |
| F5 | **Download** a released revision | browser receives the file with the sanitised original filename (`[A-Za-z0-9._-]`), content identical to what was uploaded (compare sha256) |
| F6 | **Download redline** on a revision whose file was replaced at release | the originally signed bytes |
| F7 | Open a download link after > 10 minutes | the signed URL has expired (403 from storage); a fresh click works |
| F8 | Download while signed out (paste `/api/download/<revisionId>` in a fresh private window) | redirected to `/signin` |
| F9 | Search finds extracted text: after releasing `Prototype BOM.xlsx`, search `connector` and `Northgate`; after releasing the docx, search a word from inside it | the right documents are returned; an unreleased (pending) revision's text is not searchable |
| F10 | Search edge cases: `the`, `&&`, empty | no error; `the` matches titles containing it, empty lists all current documents |

## 7. Users management (doc manager)

| ID | Steps | Expected |
|---|---|---|
| U1 | As a non-doc-manager open `/users` | only "Only doc managers can manage users." and no user data |
| U2 | As D: **Invite** email `tester+1@example.test`, name, role Quality | row appears, status *active*; History (via `/audit?entity_type=user&entity_id=<id>` with a token, or the DB) shows `user.invited`. Note: this address can never sign in; it is for the list only. |
| U3 | Invite the same email again (any case) | 409 copy "already invited" |
| U4 | Change a user's role inline; toggle Doc manager | persists on reload |
| U5 | Deactivate a user who is a pending approver on a change in *approval* | error "Finish or reassign CHG-nnnn before deactivating <name>." |
| U6 | As the only doc manager, untick your own Doc manager | 409 copy "last doc manager" |
| U7 | With two doc managers, demote the other | allowed |
| U8 | Deactivate then reactivate a user | status flips; reactivated user can sign in again |

## 8. Audit trail and data integrity (DB or API)

Use the proxy as the owner user and `.venv/bin/python` with psycopg, or `GET /audit?entity_type=change&entity_id=<id>` through the web session (not exposed in the UI; use a token via the dev bypass locally if needed).

| ID | Check | Expected |
|---|---|---|
| D1 | `SELECT action, count(*) FROM events GROUP BY action` after §5 | one event per mutation performed: `change.created`, `change.updated`, `revision.attached`, `revision.removed`, `change.approvers_set`, `change.submitted`, `change.approved`, `change.approval_complete`, `change.changes_requested`, `revision.release_file_replaced`, `change.released`, `change.commented`, `revision.downloaded`, `user.invited`, `user.updated`, `user.first_sign_in` |
| D2 | Approval rows carry `google_sub`, `email`, `file_sha256s` (sorted list), `signed_at`; voided rows have `voided_at` and `voided_reason` | yes for every approval made in §5 |
| D3 | `file_sha256s` of an approval equals the sha256 of the files attached at signing; after a release-file replacement the revision's `redline_sha256` equals that signed hash | matches (compute with `shasum -a 256` on the downloaded redline) |
| D4 | `revisions.revision_number` unique per document; exactly one `current_revision_id` per document; superseded revisions have `superseded_at` | holds after L21 |
| D5 | The `changectl_app` role cannot UPDATE/DELETE `events` (I11) | holds in production |
| D6 | No real person's email in the repo: `git grep -nE '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[a-z]{2,}' -- ':!web/package-lock.json'` | only `example.test`, `demo.example`, `example.com`-style placeholders and the `noreply@anthropic.com` commit trailer |
| D7 | The word "compliant" is absent from the UI and README: `git grep -niw compliant -- README.md web/app web/components web/lib` | no hits |

## 9. Demo path rehearsal

Run `docs/demo-script.md` end to end against production with the real accounts (Tesa's email and second account required; add both as Google test users first). Record each of its eight steps as PASS/FAIL here; the demo is "ready" only when all eight pass twice in a row from a fresh seed.

## 10. Results

Run 2026-10-21 by Claude Code against main `82abf05` plus this plan, in two rounds. Round 1 (22:15–23:30 UTC) had one signed-in account: A = D = Ben (engineering, doc manager). Round 2 (23:30–00:05 UTC) added account B, a second Google test user invited as "Ben Drolet (B)" (quality, not a doc manager), signed in from a separate Chrome profile. The demo seed was not run (it needs Tesa's email), so production started with only Ben's user row.

Test data left in production (re-seed from a fresh database before the demo): users "Tester One" (`tester+1@example.test`, cannot sign in) and B; CHG-0001, CHG-0003 and CHG-0005 in *approval* waiting on Tester One; CHG-0002, CHG-0004 and CHG-0006 *closed*; CHG-0007 in *initiate* with no files. Released documents: "Prototype BOM 2026-10-21" Rev 1, "Fixture Spec L15 2026-10-21" Rev 2, "Notes on the fixture 2026-10-21" Rev 1.

Counts: 69 PASS, 3 FAIL, 5 BLOCKED, 0 SKIP (77 IDs), plus §9 BLOCKED.

Findings beyond the FAILs: after attaching to an existing document, the attach form shows "New document" but keeps the title field hidden until a reload (L3); the first Sign out click after a page load did nothing (S5); a deactivated user sees a bare "Forbidden" box with the normal nav (S8).

| ID | Result | Note |
|---|---|---|
| A1 | PASS | 110 passed, 1 OTel `LoggingHandler` DeprecationWarning; the five pinned Review Focus tests are present. Port 5434 was held by the `build/mvp` worktree's identical Postgres 16 container (`mvp-db-1`), which was reused. |
| A2 | PASS | ruff check, ruff format --check (56 files), mypy (32 files) all clean |
| A3 | PASS | 26 passed (8 files) |
| A4 | PASS | eslint clean; build succeeded; `.next/standalone` present |
| A5 | PASS | valid, formatted |
| A6 | PASS | latest `CI` (`82abf05`) and `CI web` (`af0a91e`; path-filtered since) on main succeeded. Note: the push-triggered `CI` run on `docs/test-plan` (39685183219) failed on a flaky test, `test_replace_release_file_twice_keeps_original_redline` (`tests/test_lifecycle.py:313`), which compares two separately generated xlsx files byte for byte; openpyxl writes the current time into the file, so it fails when the second boundary moves. The PR run of the same commit passed. |
| A7 | PASS | latest `Deploy API` and `Deploy web` (workflow_dispatch, 17:56 UTC) succeeded; the earlier push-triggered pair from #1 failed |
| I1 | PASS | `{"status":"ok"}` |
| I2 | PASS | 401 |
| I3 | PASS | 200 |
| I4 | PASS | 307 to `/signin` |
| I5 | PASS | 307 to `/signin` for `/changes`, `/documents`, `/users` |
| I6 | PASS | both CNAME `ghs.googlehosted.com.`; TLS verifies without `-k` |
| I7 | PASS | all listed env and secret refs as expected; client ids match; both `allUsers` invoker; min 0, max 2 |
| I8 | PASS | five secrets; `changectl-google-oauth-client` has version 2 (version 1, the placeholder, is still enabled) |
| I9 | PASS | uniform access, PAP enforced, versioning on, soft delete 2592000 s (30 days) |
| I10 | FAIL | Observed: Cloud SQL `settings.deletionProtectionEnabled` is `false`. Postgres 16, ENTERPRISE, `db-f1-micro`, backups on, public IP with no authorized networks are as expected. `terraform/cloudsql.tf` sets only Terraform's `deletion_protection = true`, which blocks `terraform destroy` but not `gcloud sql instances delete`; the spec says "deletion protection on". |
| I11 | PASS | as `changectl_app`: UPDATE and DELETE on `events` raise InsufficientPrivilege; SELECT works; INSERT privilege granted (checked with `has_table_privilege`, no row inserted) |
| I12 | FAIL | Observed: `terraform plan` shows 0 to add, 2 to change, 0 to destroy. Both Cloud Run services: remove a service-level `scaling { manual_instance_count = 0, min_instance_count = 0 }` block. `changectl-api` also: remove container `resources.limits.cpu = "1000m"`. Neither is an image change. Cosmetic, but it is a perpetual diff. Accepted by Ben 2026-10-21: ignore (cosmetic drift). |
| I13 | PASS | two services (`changectl-api`, `changectl-web`), one instance (`changectl`) |
| S1 | PASS | after S5: Sign in with Google → Google account chooser (`prompt=select_account consent`, PKCE); Ben clicked through Google himself (the browser extension has no permission on accounts.google.com); landed on `/changes` with Changes, Documents, Users (A is a doc manager), the name and Sign out |
| S2 | BLOCKED | needs a second Google test user who is not in `users` |
| S3 | BLOCKED | needs a Google account that is not a test user |
| S4 | PASS | `/api/auth/session` has user name, email, image, id, role, isDocManager and `expires`; no id/access/refresh token fields |
| S5 | PASS | after Sign out: on `/signin`, `/api/auth/session` returns `{}`, `/changes` redirects to `/signin`. Note: the first Sign out click (right after a page load) left the session intact with no message; the second click worked. Not investigated further. |
| S6 | PASS | reload and a new tab both stay signed in as the same user |
| S7 | PASS | signed in 22:12 UTC; no requests 23:03–23:18; reload of `/changes` at 23:18 (66 min) rendered the change list with no 401 box |
| S8 | PASS | A deactivated B (not a pending approver); B's reload of `/changes` shows a "Forbidden" error box (nav still shows B's name and New change); B's signed approval on CHG-0004 still shows *signed* |
| L1 | PASS | CHG-0001 created in *initiate*; "Same as reason" copied the justification; History shows `change.created` |
| L2 | PASS | `Test Fixture Spec.docx`, 35.9 KB, *pending*, document "Test Fixture Spec 2026-10-21"; `revision.attached` sha256 matches the local file |
| L3 | PASS | CHG-0006 attached `Cable Assembly Spec.docx` to the released "Fixture Spec L15" (the select lists released documents only). Found while doing it: after an attach to an existing document the form resets the select to "New document" but keeps the title field hidden until a reload, so a following new-document attach would go up without a title |
| L4 | PASS | CHG-0007, attach to "Fixture Spec L15" while CHG-0006 held a pending revision: "That document already has a revision in an open change." |
| L5 | PASS | with B = Tester One (an invited `example.test` user who cannot sign in): listed as *pending*; A is not offered in the picker |
| L6 | PASS | "Pick at least one approver before submitting."; status stays *initiate* |
| L7 | PASS | "Attach at least one file before submitting." |
| L8 | PASS | status *approval*; Edit and Submit gone; Comment available; list shows "Waiting on: Tester One" |
| L9 | PASS | no Approve button for A; comment posted with name and date; `change.commented` |
| L10 | PASS | dialog: "You are signing as Ben Drolet (B) (<B's email>). This records your approval of CHG-0004 "Fixture spec first release 2026-10-21" with the attached files as they are now."; B *signed*; status *implementation*; History `change.approved`, `change.approval_complete` |
| L11 | PASS | on CHG-0005: an empty comment is stopped by the browser's required-field tooltip; a whitespace-only comment shows "Add a comment explaining what needs to change." The plan's first half (Approve again, then Request changes) cannot happen: once B has signed, B gets neither button (`ActionBar` shows them only while B must sign) |
| L12 | BLOCKED | verified: CHG-0005 back to *initiate*, B's row *changes requested* with time and comment, creator can Edit and Submit. Not verifiable: voiding another approver's prior approval needs a second approver who can sign in (a third account), since B cannot request changes after signing |
| L13 | PASS | A resubmitted CHG-0005, B approved: no unique-violation error. DB: B's changes-requested row voided with reason `resubmitted`, then a fresh approved row. History lists no voiding event (only `change.submitted` then `change.approved`) |
| L14 | PASS | B sees only Comment on an *implementation* change. Note: the release dialog markup is in B's DOM (closed); the server still enforces doc manager (`services/lifecycle.py:361`) |
| L15 | PASS | CHG-0004: dialog shows the signed filename, "Replace with clean file" (accept `.docx`), cut-in date defaulting to 2026-10-21; Release Rev 1 → *closed*, *Rev 1*; Documents lists it released 2026-10-21 by Ben; `change.released` |
| L16 | PASS | CHG-0002 released with `Prototype BOM rev2.xlsx`: Rev 1, *redline* tag, **Download** and **Download redline**; `revision.release_file_replaced` |
| L17 | PASS | replacement input accepts only `.xlsx`; a PDF forced in gets "A new revision must be the same file type as the document it replaces."; nothing released |
| L18 | PASS | with the cut-in date cleared, Release is disabled (`ReleaseModal.tsx:152`) and no message shows; the `cutin_required` copy ("Enter a cut-in date before releasing.") is only reachable from the server. Plan expectation should say "button disabled" |
| L19 | PASS | double-click on the signing dialog's Approve (final approver, CHG-0002): no error, status moved once, one approval row and one `change.approved` in the DB |
| L20 | PASS | double-click on Release Rev 1 (CHG-0002): one `change.released`, Rev 1. The second click's "wrong status" copy was not visible because the dialog closed; a closed change shows no Release button |
| L21 | PASS | CHG-0006 (approved by B, released by A): "Fixture Spec L15" Rev 2 current, Rev 1 `superseded_at` set (DB); searching `terminated` (only in the Rev 2 file) returns it |
| L22 | PASS | B opening `/changes/<CHG-0007>/edit` lands on `/changes/<CHG-0007>` |
| L23 | PASS | removed the revision of a brand-new document: revision gone, `revision.removed` logged, the document row deleted (DB). The "attach to existing" half is moot: that list only shows released documents, so a brand-new document never appears in it. |
| L24 | PASS | comment posted and listed on closed CHG-0002 |
| F1 | PASS | file input has `accept=".pdf,.docx,.xlsx"`, so the picker hides .txt/.png (native picker not driven) |
| F2 | PASS | PNG renamed `.pdf`: "That file couldn't be read. Upload a valid PDF, DOCX or XLSX."; no revision listed; no event |
| F3 | PASS | 26 MiB `%PDF-` file set on the input: "Files must be 25 MB or smaller" and Attach disabled before any upload |
| F4 | BLOCKED | the browser tool cannot attach a file over 10 MB from disk. A synthetic 20 MiB `%PDF-` + zero-padding file built in the page was accepted (body limit OK), but a real 20 MB PDF was not tried. That revision was then removed (L23). |
| F5 | PASS | CHG-0002 Download: `Prototype_BOM_rev2.xlsx` (sanitised), sha256 identical to the uploaded clean file |
| F6 | PASS | Download redline: `redline-Prototype_BOM_rev2.xlsx`, sha256 identical to the originally signed `Prototype BOM.xlsx` |
| F7 | BLOCKED | the browser tool redacts the signed URL's query string, so the same link could not be reopened after 10 minutes; needs a person at a browser (copy the link from chrome://downloads) |
| F8 | PASS | cookie-less `GET /api/download/<pending revision id>` → 307 to `/signin` (curl instead of a private window) |
| F9 | PASS | `connector` → BOM and fixture spec; `Northgate` → BOM; `Ohm` → fixture spec; `terminated`/`shipment` (only in the then-pending cable spec) → nothing |
| F10 | PASS | `&&` → no error, no match; empty → all three current documents; `the` → "Notes on the fixture 2026-10-21" (title match) |
| U1 | PASS | B on `/users`: only "Only doc managers can manage users."; no Users link in B's nav |
| U2 | PASS | Tester One invited as quality; row *active*; `user.invited` event in the DB |
| U3 | PASS | `Tester+1@Example.TEST`: "A user with that email already exists." |
| U4 | PASS | role → operations and Doc manager on, both persist on reload |
| U5 | PASS | "Finish or reassign CHG-0001 before deactivating Tester One." |
| U6 | PASS | "There must be at least one active doc manager."; still a doc manager |
| U7 | PASS | demoted Tester One while two doc managers existed |
| U8 | PASS | Tester One and B each deactivated and reactivated; status flips; after reactivation B's existing session lists changes again (a fresh Google sign-in was not repeated) |
| D1 | PASS | after round 2: `change.created` 7, `change.submitted` 7, `change.approvers_set` 6, `change.approved` 5, `change.approval_complete` 3, `change.changes_requested` 1, `change.released` 3, `change.commented` 2, `revision.attached` 8, `revision.removed` 1, `revision.release_file_replaced` 1, `revision.downloaded` 4, `user.invited` 2, `user.updated` 7, `user.first_sign_in` 2; rejected attempts wrote nothing. `change.updated` never fired (no change fields were edited) |
| D2 | PASS | all six approval rows have `google_sub`, `email`, sorted `file_sha256s`, `signed_at`; the voided row has `voided_at` and `voided_reason = resubmitted` |
| D3 | PASS | every live approval's `file_sha256s` equals the hashes of the files attached at signing; CHG-0002's `redline_sha256` equals the signed hash and the downloaded redline (F6) |
| D4 | PASS | no duplicate revision numbers; one current revision per document; "Fixture Spec L15" Rev 1 superseded, Rev 2 current |
| D5 | PASS | same check as I11 |
| D6 | FAIL | Observed: this file (`docs/test-plan.md`, §0 and §4) contains Ben's real address three times; main is clean. Other hits are placeholders (`example.test`, `example.com`, `demo.example`, `a@b.co` in a unit test), the `noreply@anthropic.com` trailer and the deploy service account. Accepted by Ben 2026-10-21: ignore. |
| D7 | PASS | no hits |
| §9 | BLOCKED | needs Tesa's email and a second account |

The rules in §0 say to record results in §9; this section is where the table lives.

Known limitations the executor should not file as failures (deferred review findings, tracked for a later pass): oversize uploads are buffered before the 413; attaching without a title or document maps to 415; History shows raw action codes and JSON; a user's role in the nav is a sign-in-time snapshot (8 h); the attach picker lists at most 50 documents and includes busy ones; a doc manager can deactivate themselves from the UI when another doc manager exists; a failed release-file replacement partway through is not summarised to the user; Testing-mode Google sessions need a re-sign-in weekly.
