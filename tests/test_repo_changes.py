from datetime import UTC, datetime

from models.display import display_number
from repo import changes, users


def _user(conn, email, role="engineering"):
    return users.insert(
        conn,
        email=email,
        name=email.split("@")[0],
        role=role,
        is_doc_manager=False,
        invited_by=None,
    )


def _change(conn, user, title="Swap valve"):
    return changes.insert(
        conn,
        title=title,
        description="d",
        reason="r",
        justification="j",
        created_by=str(user["id"]),
    )


def test_display_number_pads_four():
    assert display_number(1) == "CHG-0001"
    assert display_number(42) == "CHG-0042"
    assert display_number(12345) == "CHG-12345"


def test_set_approvers_replaces_set(db_conn):
    owner = _user(db_conn, "owner@example.com")
    a = _user(db_conn, "a@example.com", "quality")
    b = _user(db_conn, "b@example.com", "operations")
    change = _change(db_conn, owner)
    cid = str(change["id"])
    changes.set_approvers(db_conn, cid, [str(a["id"]), str(b["id"])], str(owner["id"]))
    rows = changes.approvers(db_conn, cid)
    assert {r["email"] for r in rows} == {"a@example.com", "b@example.com"}
    assert {r["role"] for r in rows} == {"quality", "operations"}
    changes.set_approvers(db_conn, cid, [str(b["id"])], str(owner["id"]))
    rows = changes.approvers(db_conn, cid)
    assert [r["user_id"] for r in rows] == [b["id"]]
    assert rows[0]["name"] == "b"
    changes.set_approvers(db_conn, cid, [], str(owner["id"]))
    assert changes.approvers(db_conn, cid) == []


def test_void_approvals_returns_count_and_sets_reason(db_conn):
    owner = _user(db_conn, "owner@example.com")
    a = _user(db_conn, "a@example.com")
    b = _user(db_conn, "b@example.com")
    cid = str(_change(db_conn, owner)["id"])
    for u in (a, b):
        changes.insert_approval(
            db_conn,
            change_id=cid,
            user_id=str(u["id"]),
            google_sub=f"sub-{u['email']}",
            email=u["email"],
            decision="approved",
            comment=None,
            file_sha256s=["ab" * 32],
        )
    live = changes.live_approvals(db_conn, cid)
    assert len(live) == 2
    assert live[0]["file_sha256s"] == ["ab" * 32]
    assert live[0]["signed_at"] is not None
    at = datetime.now(UTC)
    assert changes.void_approvals(db_conn, cid, "files changed", at) == 2
    assert changes.live_approvals(db_conn, cid) == []
    assert changes.void_approvals(db_conn, cid, "again", at) == 0
    voided = db_conn.execute(
        "SELECT * FROM approvals WHERE change_id = %s::uuid", (cid,)
    ).fetchall()
    assert {r["voided_reason"] for r in voided} == {"files changed"}
    assert all(r["voided_at"] == at for r in voided)


def test_open_changes_awaiting_excludes_signed(db_conn):
    owner = _user(db_conn, "owner@example.com")
    a = _user(db_conn, "a@example.com")
    uid = str(a["id"])
    c1 = _change(db_conn, owner, "one")
    c2 = _change(db_conn, owner, "two")
    c3 = _change(db_conn, owner, "three")
    for c in (c1, c2, c3):
        changes.set_approvers(db_conn, str(c["id"]), [uid], str(owner["id"]))
    for c in (c1, c2):
        changes.set_status(db_conn, str(c["id"]), "approval", at=datetime.now(UTC))
    changes.insert_approval(
        db_conn,
        change_id=str(c2["id"]),
        user_id=uid,
        google_sub="s",
        email="a@example.com",
        decision="approved",
        comment="ok",
        file_sha256s=[],
    )
    waiting = changes.open_changes_awaiting(db_conn, uid)
    assert [w["id"] for w in waiting] == [c1["id"]]
    changes.void_approvals(db_conn, str(c2["id"]), "redo", datetime.now(UTC))
    waiting = changes.open_changes_awaiting(db_conn, uid)
    assert [w["number"] for w in waiting] == sorted([c1["number"], c2["number"]])


def test_status_fields_comments_and_links(db_conn):
    owner = _user(db_conn, "owner@example.com")
    c = _change(db_conn, owner)
    cid = str(c["id"])
    at = datetime.now(UTC)
    assert changes.get(db_conn, cid)["title"] == "Swap valve"
    assert changes.get(db_conn, "00000000-0000-0000-0000-000000000000") is None
    row = changes.update_fields(db_conn, cid, title="New", reason="why")
    assert (row["title"], row["reason"], row["description"]) == ("New", "why", "d")
    assert changes.set_status(db_conn, cid, "approval", at=at)["submitted_at"] == at
    assert changes.set_status(db_conn, cid, "implementation", at=at)["approved_at"] == at
    assert changes.set_status(db_conn, cid, "closed", at=at)["closed_at"] == at
    changes.set_cutin(db_conn, cid, "2026-11-01")
    assert str(changes.get(db_conn, cid)["cutin_date"]) == "2026-11-01"
    assert [r["id"] for r in changes.list_by_status(db_conn, "closed")] == [c["id"]]
    assert changes.list_by_status(db_conn, "initiate") == []
    assert len(changes.list_by_status(db_conn, None)) == 1
    changes.insert_comment(db_conn, change_id=cid, user_id=str(owner["id"]), body="first")
    changes.insert_comment(db_conn, change_id=cid, user_id=str(owner["id"]), body="second")
    assert [x["body"] for x in changes.comments(db_conn, cid)] == ["first", "second"]
