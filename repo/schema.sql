-- changectl schema. Idempotent: safe to apply repeatedly.

CREATE EXTENSION IF NOT EXISTS pg_trgm;

DO $$ BEGIN
    CREATE TYPE user_role AS ENUM ('engineering', 'operations', 'quality', 'other');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE change_status AS ENUM ('initiate', 'approval', 'implementation', 'closed');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE approval_decision AS ENUM ('approved', 'changes_requested');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

CREATE TABLE IF NOT EXISTS users (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    email          text NOT NULL UNIQUE,
    name           text NOT NULL,
    google_sub     text UNIQUE,
    role           user_role NOT NULL,
    is_doc_manager boolean NOT NULL DEFAULT false,
    invited_by     uuid REFERENCES users(id),
    created_at     timestamptz NOT NULL DEFAULT now(),
    deactivated_at timestamptz
);

CREATE TABLE IF NOT EXISTS documents (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    title               text NOT NULL,
    created_by          uuid REFERENCES users(id),
    created_at          timestamptz NOT NULL DEFAULT now(),
    current_revision_id uuid,
    title_search        tsvector GENERATED ALWAYS AS (to_tsvector('english', title)) STORED
);

CREATE TABLE IF NOT EXISTS changes (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    number        serial UNIQUE,
    title         text NOT NULL,
    description   text NOT NULL DEFAULT '',
    reason        text NOT NULL DEFAULT '',
    justification text NOT NULL DEFAULT '',
    status        change_status NOT NULL DEFAULT 'initiate',
    created_by    uuid NOT NULL REFERENCES users(id),
    created_at    timestamptz NOT NULL DEFAULT now(),
    submitted_at  timestamptz,
    approved_at   timestamptz,
    closed_at     timestamptz,
    cutin_date    date
);

CREATE TABLE IF NOT EXISTS revisions (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id       uuid NOT NULL REFERENCES documents(id),
    revision_number   integer,
    change_id         uuid NOT NULL REFERENCES changes(id),
    original_filename text NOT NULL,
    content_type      text NOT NULL,
    byte_size         bigint NOT NULL,
    sha256            text NOT NULL,
    gcs_key           text NOT NULL,
    redline_gcs_key   text,
    redline_sha256    text,
    extracted_text    text,
    search            tsvector GENERATED ALWAYS AS (to_tsvector('english', coalesce(extracted_text, ''))) STORED,
    uploaded_by       uuid NOT NULL REFERENCES users(id),
    uploaded_at       timestamptz NOT NULL DEFAULT now(),
    released_at       timestamptz,
    released_by       uuid REFERENCES users(id),
    superseded_at     timestamptz,
    UNIQUE (document_id, revision_number)
);

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'documents_current_revision_fk') THEN
        ALTER TABLE documents
            ADD CONSTRAINT documents_current_revision_fk
            FOREIGN KEY (current_revision_id) REFERENCES revisions(id)
            DEFERRABLE INITIALLY DEFERRED;
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS change_revisions (
    change_id   uuid NOT NULL REFERENCES changes(id),
    revision_id uuid NOT NULL REFERENCES revisions(id),
    PRIMARY KEY (change_id, revision_id)
);

CREATE TABLE IF NOT EXISTS approvers (
    change_id uuid NOT NULL REFERENCES changes(id),
    user_id   uuid NOT NULL REFERENCES users(id),
    added_by  uuid NOT NULL REFERENCES users(id),
    added_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (change_id, user_id)
);

CREATE TABLE IF NOT EXISTS approvals (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    change_id     uuid NOT NULL REFERENCES changes(id),
    user_id       uuid NOT NULL REFERENCES users(id),
    google_sub    text NOT NULL,
    email         text NOT NULL,
    decision      approval_decision NOT NULL,
    comment       text,
    file_sha256s  jsonb NOT NULL DEFAULT '[]'::jsonb,
    signed_at     timestamptz NOT NULL DEFAULT now(),
    voided_at     timestamptz,
    voided_reason text
);

CREATE TABLE IF NOT EXISTS comments (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    change_id  uuid NOT NULL REFERENCES changes(id),
    user_id    uuid NOT NULL REFERENCES users(id),
    body       text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS events (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    at            timestamptz NOT NULL DEFAULT now(),
    actor_user_id uuid REFERENCES users(id),
    entity_type   text NOT NULL,
    entity_id     uuid,
    action        text NOT NULL,
    detail        jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE UNIQUE INDEX IF NOT EXISTS approvals_one_live_per_user
    ON approvals (change_id, user_id) WHERE voided_at IS NULL;
CREATE INDEX IF NOT EXISTS revisions_search_idx ON revisions USING GIN (search);
CREATE INDEX IF NOT EXISTS documents_title_search_idx ON documents USING GIN (title_search);
CREATE INDEX IF NOT EXISTS documents_title_trgm_idx ON documents USING GIN (title gin_trgm_ops);
CREATE INDEX IF NOT EXISTS revisions_document_idx ON revisions (document_id);
CREATE INDEX IF NOT EXISTS revisions_change_idx ON revisions (change_id);
CREATE INDEX IF NOT EXISTS events_entity_idx ON events (entity_type, entity_id, at);
