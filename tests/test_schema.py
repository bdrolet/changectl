from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import psycopg
import pytest
from conftest import TEST_DSN, apply_sql

SCHEMA = Path(__file__).resolve().parent.parent / "repo" / "schema.sql"

TABLES = {
    "users",
    "documents",
    "revisions",
    "changes",
    "change_revisions",
    "approvers",
    "approvals",
    "comments",
    "events",
}


def _app_dsn() -> str:
    parts = urlsplit(TEST_DSN or "")
    return urlunsplit(parts._replace(netloc=f"changectl_app:app@{parts.hostname}:{parts.port}"))


def _user(conn, email: str):
    return conn.execute(
        "INSERT INTO users (email, name, role) VALUES (%s, %s, 'engineering') RETURNING id",
        (email, email),
    ).fetchone()["id"]


def test_tables_exist(db_conn):
    rows = db_conn.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
    ).fetchall()
    assert TABLES <= {r["table_name"] for r in rows}


def test_events_append_only(db_conn):
    db_conn.commit()
    with psycopg.connect(_app_dsn(), autocommit=True) as app:
        app.execute("INSERT INTO events (entity_type, action) VALUES ('change', 'created')")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            app.execute("UPDATE events SET action = 'x'")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            app.execute("DELETE FROM events")
        # ordinary tables remain writable
        app.execute("INSERT INTO users (email, name, role) VALUES ('a@x', 'A', 'other')")


def test_schema_idempotent(db_conn):
    apply_sql(db_conn, SCHEMA)
    apply_sql(db_conn, SCHEMA)
    db_conn.commit()


def test_one_live_approval_per_user(db_conn):
    creator = _user(db_conn, "c@x")
    approver = _user(db_conn, "a@x")
    change_id = db_conn.execute(
        "INSERT INTO changes (title, created_by) VALUES ('t', %s) RETURNING id", (creator,)
    ).fetchone()["id"]
    sql = (
        "INSERT INTO approvals (change_id, user_id, google_sub, email, decision, voided_at) "
        "VALUES (%s, %s, 'sub', 'a@x', 'approved', %s)"
    )
    db_conn.execute(sql, (change_id, approver, None))
    with pytest.raises(psycopg.errors.UniqueViolation):
        db_conn.execute("SAVEPOINT s")
        db_conn.execute(sql, (change_id, approver, None))
    db_conn.execute("ROLLBACK TO SAVEPOINT s")
    db_conn.execute(sql, (change_id, approver, "2026-01-01T00:00:00Z"))


def test_roles_sql_never_changes_an_existing_role_password(db_conn):
    """Terraform owns the deployed password; re-running roles.sql must not reset it."""
    roles = (SCHEMA.parent / "roles.sql").read_text()
    db_conn.execute(roles.replace("__APP_PASSWORD__", "throwaway"))
    db_conn.commit()
    with psycopg.connect(_app_dsn(), autocommit=True) as app:
        assert app.execute("SELECT 1").fetchone() == (1,)
