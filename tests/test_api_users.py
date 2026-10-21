import io

import openpyxl

from clients.storage import LocalStorage
from repo import events, users
from services import lifecycle


def _xlsx() -> bytes:
    wb = openpyxl.Workbook()
    wb.active["A1"] = "Part"
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _body(**over):
    return {
        "email": "new@example.test",
        "name": "New Person",
        "role": "operations",
        "is_doc_manager": False,
        **over,
    }


def test_invite_requires_doc_manager(api_client, seed_users):
    api_client.as_user("creator@example.test")
    assert api_client.client.post("/users", json=_body()).status_code == 403
    assert (
        api_client.client.patch(
            f"/users/{seed_users['ops']['id']}", json={"role": "quality"}
        ).status_code
        == 403
    )
    r = api_client.client.get("/users")
    assert r.status_code == 200
    names = [u["name"] for u in r.json()]
    assert names == sorted(names)
    assert len(names) == 4


def test_invite_lowercases_and_dedupes(api_client, seed_users, db_conn):
    api_client.as_user("docmgr@example.test")
    r = api_client.client.post("/users", json=_body(email="New@Example.TEST"))
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == "new@example.test"
    assert body["role"] == "operations"
    assert body["deactivated"] is False
    evs = events.for_entity(db_conn, "user", body["id"])
    assert [e["action"] for e in evs] == ["user.invited"]
    assert evs[0]["detail"]["email"] == "new@example.test"

    dup = api_client.client.post("/users", json=_body(email="NEW@example.test"))
    assert dup.status_code == 409
    assert dup.json()["detail"] == "duplicate_email"

    assert api_client.client.post("/users", json=_body(role="wizard")).status_code == 422
    assert api_client.client.post("/users", json=_body(email="nope")).status_code == 422
    assert api_client.client.post("/users", json=_body(name="")).status_code == 422


def test_deactivate_pending_approver_409_lists_changes(api_client, seed_users, db_conn, tmp_path):
    creator = seed_users["creator"]
    change = lifecycle.create_change(
        db_conn, creator, title="Swap valve", description="d", reason="r", justification="j"
    )
    cid = str(change["id"])
    lifecycle.attach_revision(
        db_conn,
        creator,
        cid,
        filename="proc.xlsx",
        data=_xlsx(),
        storage=LocalStorage(tmp_path),
        title="Procedure",
    )
    lifecycle.set_approvers(db_conn, creator, cid, [str(seed_users["quality"]["id"])])
    lifecycle.submit(db_conn, creator, cid)

    api_client.as_user("docmgr@example.test")
    qid = seed_users["quality"]["id"]
    r = api_client.client.patch(f"/users/{qid}", json={"deactivated": True})
    assert r.status_code == 409
    body = r.json()
    assert body["detail"] == "pending_approver"
    assert body["changes"] == [f"CHG-{change['number']:04d}"]

    # an uninvolved user can be deactivated, and reactivated
    oid = seed_users["ops"]["id"]
    r = api_client.client.patch(f"/users/{oid}", json={"deactivated": True})
    assert r.status_code == 200 and r.json()["deactivated"] is True
    r = api_client.client.patch(f"/users/{oid}", json={"deactivated": False, "role": "other"})
    assert r.status_code == 200
    assert r.json()["deactivated"] is False and r.json()["role"] == "other"
    actions = [e["action"] for e in events.for_entity(db_conn, "user", str(oid))]
    assert actions == ["user.updated", "user.updated"]

    missing = api_client.client.patch(
        "/users/00000000-0000-0000-0000-000000000000", json={"role": "other"}
    )
    assert missing.status_code == 404
    assert api_client.client.patch("/users/bogus", json={}).status_code == 404


def test_last_doc_manager_cannot_demote_self(api_client, seed_users, db_conn):
    api_client.as_user("docmgr@example.test")
    me = seed_users["docmgr"]["id"]
    r = api_client.client.patch(f"/users/{me}", json={"is_doc_manager": False})
    assert r.status_code == 409
    assert r.json()["detail"] == "last_doc_manager"
    r = api_client.client.patch(f"/users/{me}", json={"deactivated": True})
    assert r.status_code == 409
    assert r.json()["detail"] == "last_doc_manager"

    # with a second doc manager, demoting self is allowed
    users.update(db_conn, str(seed_users["quality"]["id"]), is_doc_manager=True)
    r = api_client.client.patch(f"/users/{me}", json={"is_doc_manager": False})
    assert r.status_code == 200
    assert r.json()["is_doc_manager"] is False
