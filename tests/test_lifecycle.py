import io
from datetime import date

import openpyxl
import pytest

from clients.storage import LocalStorage
from models.errors import LifecycleError
from repo import changes, documents, events, users
from services import extract, lifecycle


def xlsx_bytes(text: str = "Part") -> bytes:
    wb = openpyxl.Workbook()
    wb.active["A1"] = text
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def pdf_bytes(text: str = "hello pdf") -> bytes:
    doc = extract.pymupdf.open()
    doc.new_page().insert_text((72, 72), text)
    data = doc.tobytes()
    doc.close()
    return data


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
        "b": _user(db_conn, "b@example.com", "operations"),
        "docmgr": _user(db_conn, "docmgr@example.com", "quality", True),
    }


@pytest.fixture
def storage(tmp_path):
    return LocalStorage(tmp_path)


def _new_change(conn, creator):
    return lifecycle.create_change(
        conn, creator, title="Swap valve", description="d", reason="r", justification="j"
    )


def _submitted(conn, team, storage, **attach):
    change = _new_change(conn, team["creator"])
    cid = str(change["id"])
    rev = lifecycle.attach_revision(
        conn,
        team["creator"],
        cid,
        filename="proc.xlsx",
        data=xlsx_bytes(),
        storage=storage,
        title="Procedure",
        **attach,
    )
    lifecycle.set_approvers(
        conn, team["creator"], cid, [str(team["a"]["id"]), str(team["b"]["id"])]
    )
    lifecycle.submit(conn, team["creator"], cid)
    return cid, rev


def _approve(conn, user, cid):
    return lifecycle.approve(conn, user, cid, google_sub=f"sub-{user['email']}", comment=None)


def _code(exc_info):
    return exc_info.value.code


def test_full_initial_release_flow(db_conn, team, storage):
    cid, rev = _submitted(db_conn, team, storage)
    assert changes.get(db_conn, cid)["status"] == "approval"
    _approve(db_conn, team["a"], cid)
    assert changes.get(db_conn, cid)["status"] == "approval"
    _approve(db_conn, team["b"], cid)
    assert changes.get(db_conn, cid)["status"] == "implementation"
    done = lifecycle.release(db_conn, team["docmgr"], cid, cutin_date=date(2026, 11, 1))
    assert done["status"] == "closed"
    released = documents.revision(db_conn, str(rev["id"]))
    assert released["revision_number"] == 1
    doc = documents.document(db_conn, str(rev["document_id"]))
    assert doc["current_revision_id"] == rev["id"]
    assert changes.get(db_conn, cid)["cutin_date"] == date(2026, 11, 1)
    actions = {e["action"] for e in events.for_change(db_conn, cid)}
    assert {"change.created", "change.submitted", "change.approval_complete"} <= actions
    assert "change.released" in actions
    approvals = changes.live_approvals(db_conn, cid)
    assert approvals[0]["file_sha256s"] == [rev["sha256"]]


def test_cannot_approve_own_change(db_conn, team):
    cid = str(_new_change(db_conn, team["creator"])["id"])
    with pytest.raises(LifecycleError) as e:
        lifecycle.set_approvers(db_conn, team["creator"], cid, [str(team["creator"]["id"])])
    assert _code(e) == "self_approval"


def test_submit_requires_approvers_and_revisions(db_conn, team, storage):
    cid = str(_new_change(db_conn, team["creator"])["id"])
    with pytest.raises(LifecycleError) as e:
        lifecycle.submit(db_conn, team["creator"], cid)
    assert _code(e) == "no_approvers"
    lifecycle.set_approvers(db_conn, team["creator"], cid, [str(team["a"]["id"])])
    with pytest.raises(LifecycleError) as e:
        lifecycle.submit(db_conn, team["creator"], cid)
    assert _code(e) == "no_revisions"
    lifecycle.attach_revision(
        db_conn,
        team["creator"],
        cid,
        filename="p.xlsx",
        data=xlsx_bytes(),
        storage=storage,
        title="P",
    )
    assert lifecycle.submit(db_conn, team["creator"], cid)["status"] == "approval"


def test_approve_is_idempotent(db_conn, team, storage):
    cid, _ = _submitted(db_conn, team, storage)
    first = _approve(db_conn, team["a"], cid)
    second = _approve(db_conn, team["a"], cid)
    assert first["id"] == second["id"]
    assert len(changes.live_approvals(db_conn, cid)) == 1
    assert [e["action"] for e in events.for_change(db_conn, cid)].count("change.approved") == 1


def test_request_changes_voids_and_reopens(db_conn, team, storage):
    cid, _ = _submitted(db_conn, team, storage)
    _approve(db_conn, team["a"], cid)
    lifecycle.request_changes(
        db_conn, team["b"], cid, google_sub="sub-b", comment="fix the torque value"
    )
    assert changes.get(db_conn, cid)["status"] == "initiate"
    voided = db_conn.execute(
        "SELECT * FROM approvals WHERE voided_at IS NOT NULL AND change_id = %s::uuid", (cid,)
    ).fetchall()
    assert len(voided) == 1
    assert voided[0]["voided_reason"] == "changes_requested_by:b@example.com"
    live = changes.live_approvals(db_conn, cid)
    assert [r["decision"] for r in live] == ["changes_requested"]
    # resubmission voids the stale changes_requested row so b may approve later
    lifecycle.submit(db_conn, team["creator"], cid)
    assert changes.live_approvals(db_conn, cid) == []
    _approve(db_conn, team["b"], cid)


def test_locked_after_submit(db_conn, team, storage):
    cid, _ = _submitted(db_conn, team, storage)
    with pytest.raises(LifecycleError) as e:
        lifecycle.update_change(db_conn, team["creator"], cid, title="new")
    assert _code(e) == "locked"


def test_attach_rejects_oversize_and_bad_type(db_conn, team, storage):
    cid = str(_new_change(db_conn, team["creator"])["id"])
    big = b"%PDF-" + b"0" * lifecycle.MAX_UPLOAD_BYTES
    with pytest.raises(LifecycleError) as e:
        lifecycle.attach_revision(
            db_conn, team["creator"], cid, filename="x.pdf", data=big, storage=storage, title="X"
        )
    assert _code(e) == "too_large"
    with pytest.raises(LifecycleError) as e:
        lifecycle.attach_revision(
            db_conn,
            team["creator"],
            cid,
            filename="x.html",
            data=b"<html>",
            storage=storage,
            title="X",
        )
    assert _code(e) == "invalid_file"


def test_document_busy_blocks_second_pending_revision(db_conn, team, storage):
    cid, rev = _submitted(db_conn, team, storage)
    other = str(_new_change(db_conn, team["creator"])["id"])
    with pytest.raises(LifecycleError) as e:
        lifecycle.attach_revision(
            db_conn,
            team["creator"],
            other,
            filename="p2.xlsx",
            data=xlsx_bytes("v2"),
            storage=storage,
            document_id=str(rev["document_id"]),
        )
    assert _code(e) == "document_busy"


def test_replace_release_file_type_mismatch(db_conn, team, storage):
    cid, rev = _submitted(db_conn, team, storage)
    _approve(db_conn, team["a"], cid)
    _approve(db_conn, team["b"], cid)
    with pytest.raises(LifecycleError) as e:
        lifecycle.replace_release_file(
            db_conn,
            team["docmgr"],
            cid,
            str(rev["id"]),
            filename="signed.pdf",
            data=pdf_bytes(),
            storage=storage,
        )
    assert _code(e) == "type_mismatch"
    new = xlsx_bytes("signed")
    out = lifecycle.replace_release_file(
        db_conn,
        team["docmgr"],
        cid,
        str(rev["id"]),
        filename="signed.xlsx",
        data=new,
        storage=storage,
    )
    assert out["redline_sha256"] == rev["sha256"]
    assert out["redline_gcs_key"] == rev["gcs_key"]
    assert out["gcs_key"] != rev["gcs_key"]
    assert storage.get(out["gcs_key"]) == new


def test_revision_flow_supersedes(db_conn, team, storage):
    cid, rev = _submitted(db_conn, team, storage)
    _approve(db_conn, team["a"], cid)
    _approve(db_conn, team["b"], cid)
    lifecycle.release(db_conn, team["docmgr"], cid, cutin_date=date(2026, 11, 1))
    c2 = str(_new_change(db_conn, team["creator"])["id"])
    rev2 = lifecycle.attach_revision(
        db_conn,
        team["creator"],
        c2,
        filename="proc2.xlsx",
        data=xlsx_bytes("v2"),
        storage=storage,
        document_id=str(rev["document_id"]),
    )
    lifecycle.set_approvers(db_conn, team["creator"], c2, [str(team["a"]["id"])])
    lifecycle.submit(db_conn, team["creator"], c2)
    _approve(db_conn, team["a"], c2)
    lifecycle.release(db_conn, team["docmgr"], c2, cutin_date=date(2026, 12, 1))
    doc = documents.document(db_conn, str(rev["document_id"]))
    assert doc["current_revision_id"] == rev2["id"]
    assert documents.revision(db_conn, str(rev2["id"]))["revision_number"] == 2
    assert documents.revision(db_conn, str(rev["id"]))["superseded_at"] is not None


def test_release_requires_doc_manager(db_conn, team, storage):
    cid, _ = _submitted(db_conn, team, storage)
    _approve(db_conn, team["a"], cid)
    _approve(db_conn, team["b"], cid)
    with pytest.raises(LifecycleError) as e:
        lifecycle.release(db_conn, team["a"], cid, cutin_date=date(2026, 11, 1))
    assert _code(e) == "forbidden"
