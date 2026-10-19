from repo import users


def _make(conn, email="Ann@Example.com"):
    return users.insert(
        conn,
        email=email,
        name="Ann",
        role="engineering",
        is_doc_manager=False,
        invited_by=None,
    )


def test_insert_and_by_email_case_insensitive(db_conn):
    row = _make(db_conn)
    assert row["email"] == "ann@example.com"
    assert row["role"] == "engineering"
    assert users.by_email(db_conn, "ANN@example.COM")["id"] == row["id"]
    assert users.by_id(db_conn, str(row["id"]))["email"] == "ann@example.com"
    assert users.by_email(db_conn, "nobody@example.com") is None
    assert [u["id"] for u in users.list_all(db_conn)] == [row["id"]]
    users.set_google_sub(db_conn, str(row["id"]), "sub-1")
    assert users.by_id(db_conn, str(row["id"]))["google_sub"] == "sub-1"


def test_update_deactivates_and_reactivates(db_conn):
    row = _make(db_conn)
    uid = str(row["id"])
    assert row["deactivated_at"] is None
    off = users.update(db_conn, uid, deactivated=True, role="quality")
    assert off["deactivated_at"] is not None
    assert off["role"] == "quality"
    again = users.update(db_conn, uid, deactivated=True)
    assert again["deactivated_at"] == off["deactivated_at"]
    on = users.update(db_conn, uid, deactivated=False, is_doc_manager=True)
    assert on["deactivated_at"] is None
    assert on["is_doc_manager"] is True
    assert on["role"] == "quality"
