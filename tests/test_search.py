from datetime import date

import pytest

from clients.storage import LocalStorage
from repo import users
from services import lifecycle, search
from tests.test_lifecycle import xlsx_bytes


def _user(conn, email, role, doc_manager=False):
    return users.insert(
        conn,
        email=email,
        name=email.split("@")[0],
        role=role,
        is_doc_manager=doc_manager,
        invited_by=None,
    )


@pytest.fixture
def team(db_conn):
    return {
        "creator": _user(db_conn, "creator@example.com", "engineering"),
        "a": _user(db_conn, "a@example.com", "quality"),
        "docmgr": _user(db_conn, "docmgr@example.com", "quality", True),
    }


@pytest.fixture
def storage(tmp_path):
    return LocalStorage(tmp_path)


def _submitted(conn, team, storage, title, text, document_id=None):
    change = lifecycle.create_change(
        conn,
        team["creator"],
        title=f"Change {title}",
        description="d",
        reason="r",
        justification="j",
    )
    cid = str(change["id"])
    rev = lifecycle.attach_revision(
        conn,
        team["creator"],
        cid,
        filename="proc.xlsx",
        data=xlsx_bytes(text),
        storage=storage,
        title=None if document_id else title,
        document_id=document_id,
    )
    lifecycle.set_approvers(conn, team["creator"], cid, [str(team["a"]["id"])])
    lifecycle.submit(conn, team["creator"], cid)
    return cid, rev


def _released(conn, team, storage, title, text, document_id=None):
    cid, rev = _submitted(conn, team, storage, title, text, document_id)
    lifecycle.approve(conn, team["a"], cid, google_sub="sub-a", comment=None)
    lifecycle.release(conn, team["docmgr"], cid, cutin_date=date(2026, 11, 1))
    return cid, rev


def test_search_matches_extracted_text(db_conn, team, storage):
    _, rev = _released(db_conn, team, storage, "Harness", "J4 connector")
    _released(db_conn, team, storage, "Other", "nothing relevant")
    rows = search.search_documents(db_conn, "connector")
    assert [r["document_id"] for r in rows] == [rev["document_id"]]
    row = rows[0]
    assert row["title"] == "Harness"
    assert row["revision_number"] == 1
    assert row["released_by_name"] == "docmgr"
    assert row["original_filename"] == "proc.xlsx"
    assert row["current_revision_id"] == rev["id"]
    assert row["rank"] > 0


def test_search_excludes_unreleased(db_conn, team, storage):
    _submitted(db_conn, team, storage, "Draft doc", "connector")
    assert search.search_documents(db_conn, "connector") == []
    assert search.search_documents(db_conn, "") == []


def test_search_title_weighted_first(db_conn, team, storage):
    _released(db_conn, team, storage, "Gasket", "torque valve spec")
    _, titled = _released(db_conn, team, storage, "Valve", "gasket notes")
    rows = search.search_documents(db_conn, "valve")
    assert rows[0]["document_id"] == titled["document_id"]
    assert len(rows) == 2


def test_search_stopwords_fall_back_to_ilike(db_conn, team, storage):
    _, rev = _released(db_conn, team, storage, "The BOM", "parts")
    _released(db_conn, team, storage, "Gasket", "parts")
    rows = search.search_documents(db_conn, "the")
    assert [r["document_id"] for r in rows] == [rev["document_id"]]
    assert rows[0]["rank"] == 0.0
    assert search.search_documents(db_conn, "100%") == []


def test_search_empty_lists_all_current(db_conn, team, storage):
    _, first = _released(db_conn, team, storage, "First", "a")
    _, second = _released(db_conn, team, storage, "Second", "b")
    rows = search.search_documents(db_conn, "   ")
    assert [r["document_id"] for r in rows] == [second["document_id"], first["document_id"]]
    assert all(r["rank"] == 0.0 for r in rows)
    assert len(search.search_documents(db_conn, "", limit=1)) == 1


def test_document_detail_lists_revisions_with_change_numbers(db_conn, team, storage):
    cid1, rev1 = _released(db_conn, team, storage, "Proc", "v1")
    doc_id = str(rev1["document_id"])
    cid2, rev2 = _submitted(db_conn, team, storage, "Proc", "v2", document_id=doc_id)
    detail = search.document_detail(db_conn, doc_id)
    assert detail["title"] == "Proc"
    revs = detail["revisions"]
    assert [r["id"] for r in revs] == [rev2["id"], rev1["id"]]
    pending, released = revs
    assert pending["change_status"] == "approval"
    assert pending["approvals"] == []
    assert released["change_number"] == 1
    assert released["change_display"] == "CHG-0001"
    assert released["change_title"] == "Change Proc"
    assert released["change_status"] == "closed"
    assert released["cutin_date"] == date(2026, 11, 1)
    assert [a["name"] for a in released["approvals"]] == ["a"]
    assert released["approvals"][0]["email"] == "a@example.com"
    assert released["approvals"][0]["signed_at"] is not None
    assert search.document_detail(db_conn, "00000000-0000-0000-0000-000000000000") is None
