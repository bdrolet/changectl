"""Shared fixtures: a clean Postgres for DB tests, and no accidental real DB."""

import os
from pathlib import Path

import psycopg
import pytest
from psycopg.rows import dict_row

REPO_ROOT = Path(__file__).resolve().parent.parent
TEST_DSN = os.environ.get("CHANGECTL_TEST_DSN")

_DB_ENV = (
    "CLOUD_SQL_CONNECTION_NAME",
    "POSTGRES_HOST",
    "POSTGRES_PORT",
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
)


@pytest.fixture(autouse=True)
def _no_real_db(monkeypatch):
    for name in _DB_ENV:
        monkeypatch.delenv(name, raising=False)


def apply_sql(conn, path: Path) -> None:
    """Execute a whole SQL file on the connection, if it exists."""
    if not path.exists():
        return
    sql = path.read_text()
    if path.name == "roles.sql":
        sql = sql.replace("__APP_PASSWORD__", "app")
    conn.execute(sql)


@pytest.fixture
def raw_conn():
    """An open connection to an empty test database. Skips if no DSN is set."""
    if not TEST_DSN:
        pytest.skip("CHANGECTL_TEST_DSN not set")
    conn = psycopg.connect(TEST_DSN, row_factory=dict_row)
    conn.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
    conn.commit()
    yield conn
    conn.rollback()
    conn.close()


@pytest.fixture
def db_conn(raw_conn):
    """Schema and roles applied (whichever of the files exist yet)."""
    apply_sql(raw_conn, REPO_ROOT / "repo" / "schema.sql")
    apply_sql(raw_conn, REPO_ROOT / "repo" / "roles.sql")
    raw_conn.commit()
    return raw_conn
