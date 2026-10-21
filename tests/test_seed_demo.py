import io
import subprocess
import sys
from pathlib import Path

import openpyxl
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


def _open_change_approvers(conn) -> list[dict]:
    return conn.execute(
        """
        SELECT u.email,
               EXISTS (
                   SELECT 1 FROM approvals p
                   WHERE p.change_id = a.change_id AND p.user_id = a.user_id
                     AND p.decision = 'approved' AND p.voided_at IS NULL
               ) AS signed
        FROM approvers a
        JOIN changes c ON c.id = a.change_id
        JOIN users u ON u.id = a.user_id
        WHERE c.title = %s
        ORDER BY u.email
        """,
        (seed_demo.OPEN_CHANGE,),
    ).fetchall()


@pytest.mark.parametrize(
    "second, live", [("second@example.test", "second@example.test"), (None, "tesa@example.test")]
)
def test_open_change_has_a_live_pending_approver(db_conn, tmp_path, monkeypatch, second, live):
    monkeypatch.setenv("SEED_TESA_EMAIL", "tesa@example.test")
    monkeypatch.setenv("SEED_BEN_EMAIL", "ben@example.test")
    if second:
        monkeypatch.setenv("SEED_SECOND_EMAIL", second)
    else:
        monkeypatch.delenv("SEED_SECOND_EMAIL", raising=False)
    seed_demo.main(conn=db_conn, storage=LocalStorage(tmp_path))
    rows = _open_change_approvers(db_conn)
    pending_live = [
        r["email"] for r in rows if not r["signed"] and not r["email"].endswith("@demo.example")
    ]
    assert pending_live == [live]
    assert {r["email"]: r["signed"] for r in rows}["marcus@demo.example"] is True


def test_demo_files_cli_writes_the_presenter_files(tmp_path):
    script = Path(__file__).resolve().parent.parent / "scripts" / "demo_files.py"
    subprocess.run([sys.executable, str(script), "--out", str(tmp_path)], check=True)
    names = sorted(p.name for p in tmp_path.iterdir())
    assert names == [
        "Cable Assembly Spec.docx",
        "Prototype BOM rev2.xlsx",
        "Prototype BOM.xlsx",
        "Supplier Spec - Connector.pdf",
        "Test Fixture Spec.docx",
    ]
    rev2 = openpyxl.load_workbook(io.BytesIO((tmp_path / "Prototype BOM rev2.xlsx").read_bytes()))
    assert "Changes" in rev2.sheetnames
