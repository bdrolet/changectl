import sys
from pathlib import Path

import pytest

from clients.storage import LocalStorage
from services import search

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import seed_demo  # noqa: E402


def _counts(conn) -> dict[str, int]:
    def n(sql: str) -> int:
        return conn.execute(sql).fetchone()["n"]

    return {
        "users": n("SELECT count(*) AS n FROM users"),
        "released": n("SELECT count(*) AS n FROM documents WHERE current_revision_id IS NOT NULL"),
        "changes": n("SELECT count(*) AS n FROM changes"),
        "closed": n("SELECT count(*) AS n FROM changes WHERE status = 'closed'"),
        "approval": n("SELECT count(*) AS n FROM changes WHERE status = 'approval'"),
        "approvals": n("SELECT count(*) AS n FROM approvals"),
    }


def test_seed_is_idempotent(db_conn, tmp_path, monkeypatch):
    monkeypatch.setenv("SEED_TESA_EMAIL", "tesa@example.test")
    monkeypatch.setenv("SEED_BEN_EMAIL", "ben@example.test")
    monkeypatch.setenv("SEED_SECOND_EMAIL", "second@example.test")

    first = seed_demo.main(conn=db_conn, storage=LocalStorage(tmp_path))
    counts = _counts(db_conn)
    assert counts["released"] == 3
    assert counts["changes"] == 4
    assert counts["closed"] == 3
    assert counts["approval"] == 1
    assert counts["users"] == 6
    assert first == {"users": 6, "documents": 3, "changes": 4}

    second = seed_demo.main(conn=db_conn, storage=LocalStorage(tmp_path))
    assert _counts(db_conn) == counts
    assert second == first

    hits = search.search_documents(db_conn, "connector")
    assert "Prototype BOM" in [h["title"] for h in hits]


def test_seed_without_second_account(db_conn, tmp_path, monkeypatch):
    monkeypatch.setenv("SEED_TESA_EMAIL", "tesa@example.test")
    monkeypatch.setenv("SEED_BEN_EMAIL", "ben@example.test")
    monkeypatch.delenv("SEED_SECOND_EMAIL", raising=False)
    assert seed_demo.main(conn=db_conn, storage=LocalStorage(tmp_path))["users"] == 5


def test_seed_requires_emails(db_conn, tmp_path, monkeypatch):
    monkeypatch.delenv("SEED_TESA_EMAIL", raising=False)
    monkeypatch.delenv("SEED_BEN_EMAIL", raising=False)
    with pytest.raises(SystemExit) as exc:
        seed_demo.main(conn=db_conn, storage=LocalStorage(tmp_path))
    assert exc.value.code == 2
