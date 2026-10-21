from datetime import UTC, datetime

from repo import documents, users


def _user(conn):
    return users.insert(
        conn,
        email="ann@example.com",
        name="Ann",
        role="engineering",
        is_doc_manager=True,
        invited_by=None,
    )


def _change(conn, user_id, status="initiate"):
    return conn.execute(
        "INSERT INTO changes (title, created_by, status) VALUES (%s, %s::uuid, %s::change_status) RETURNING *",
        ("A change", user_id, status),
    ).fetchone()


def _rev(conn, doc, change, user, name="a.pdf"):
    return documents.insert_revision(
        conn,
        document_id=str(doc["id"]),
        change_id=str(change["id"]),
        original_filename=name,
        content_type="application/pdf",
        byte_size=10,
        sha256="ab" * 32,
        gcs_key=f"k/{name}",
        extracted_text="hello",
        uploaded_by=str(user["id"]),
    )


def _release(conn, rev, number, user):
    return documents.release(
        conn,
        str(rev["id"]),
        revision_number=number,
        released_by=str(user["id"]),
        released_at=datetime.now(UTC),
    )


def test_next_revision_number_starts_at_one(db_conn):
    user = _user(db_conn)
    doc = documents.insert_document(db_conn, title="SOP", created_by=str(user["id"]))
    assert documents.document(db_conn, str(doc["id"]))["title"] == "SOP"
    assert documents.document(db_conn, "00000000-0000-0000-0000-000000000000") is None
    assert documents.next_revision_number(db_conn, str(doc["id"])) == 1


def test_release_and_supersede(db_conn):
    user = _user(db_conn)
    doc = documents.insert_document(db_conn, title="SOP", created_by=str(user["id"]))
    did = str(doc["id"])
    change = _change(db_conn, str(user["id"]))
    r1 = _release(db_conn, _rev(db_conn, doc, change, user, "1.pdf"), 1, user)
    documents.supersede_current(db_conn, did, str(r1["id"]), datetime.now(UTC))
    assert documents.document(db_conn, did)["current_revision_id"] == r1["id"]
    assert documents.next_revision_number(db_conn, did) == 2

    r2 = _release(db_conn, _rev(db_conn, doc, change, user, "2.pdf"), 2, user)
    assert r2["revision_number"] == 2
    assert r2["released_by"] == user["id"]
    documents.supersede_current(db_conn, did, str(r2["id"]), datetime.now(UTC))
    assert documents.revision(db_conn, str(r1["id"]))["superseded_at"] is not None
    assert documents.revision(db_conn, str(r2["id"]))["superseded_at"] is None
    assert documents.document(db_conn, did)["current_revision_id"] == r2["id"]
    rows = documents.revisions_for_document(db_conn, did)
    assert [r["revision_number"] for r in rows] == [2, 1]
    assert rows[0]["change_number"] == change["number"]
    assert rows[0]["change_status"] == "initiate"
    assert len(documents.revisions_for_change(db_conn, str(change["id"]))) == 2


def test_pending_revision_exists_true_until_release(db_conn):
    user = _user(db_conn)
    doc = documents.insert_document(db_conn, title="SOP", created_by=str(user["id"]))
    did = str(doc["id"])
    change = _change(db_conn, str(user["id"]))
    assert documents.pending_revision_exists(db_conn, did) is False
    rev = _rev(db_conn, doc, change, user)
    assert documents.pending_revision_exists(db_conn, did) is True
    assert documents.revisions_for_document(db_conn, did)[0]["id"] == rev["id"]
    _release(db_conn, rev, 1, user)
    assert documents.pending_revision_exists(db_conn, did) is False


def test_pending_ignores_closed_change_and_delete_removes_links(db_conn):
    user = _user(db_conn)
    doc = documents.insert_document(db_conn, title="SOP", created_by=str(user["id"]))
    did = str(doc["id"])
    closed = _change(db_conn, str(user["id"]), "closed")
    stale = _rev(db_conn, doc, closed, user)
    assert documents.pending_revision_exists(db_conn, did) is False
    db_conn.execute(
        "INSERT INTO change_revisions (change_id, revision_id) VALUES (%s::uuid, %s::uuid)",
        (str(closed["id"]), str(stale["id"])),
    )
    documents.delete_revision(db_conn, str(stale["id"]))
    assert documents.revision(db_conn, str(stale["id"])) is None


def test_set_release_file(db_conn):
    user = _user(db_conn)
    doc = documents.insert_document(db_conn, title="SOP", created_by=str(user["id"]))
    change = _change(db_conn, str(user["id"]))
    rev = _rev(db_conn, doc, change, user)
    row = documents.set_release_file(
        db_conn,
        str(rev["id"]),
        gcs_key="new/key",
        sha256="cd" * 32,
        content_type="text/plain",
        byte_size=5,
        original_filename="n.txt",
        extracted_text=None,
        redline_gcs_key="r/key",
        redline_sha256="ef" * 32,
    )
    assert row["gcs_key"] == "new/key"
    assert row["redline_gcs_key"] == "r/key"
    assert row["extracted_text"] is None
