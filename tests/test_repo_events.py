import uuid

from repo import events


def test_record_and_for_entity_order(db_conn):
    eid = str(uuid.uuid4())
    first = events.record(
        db_conn, actor_user_id=None, entity_type="change", entity_id=eid, action="created"
    )
    second = events.record(
        db_conn,
        actor_user_id=None,
        entity_type="change",
        entity_id=eid,
        action="submitted",
        detail={"k": 1},
    )
    assert first["detail"] == {}
    rows = events.for_entity(db_conn, "change", eid)
    assert [r["id"] for r in rows] == [second["id"], first["id"]]
    assert rows[0]["detail"] == {"k": 1}


def test_for_change_includes_detail_linked(db_conn):
    cid = str(uuid.uuid4())
    direct = events.record(
        db_conn, actor_user_id=None, entity_type="change", entity_id=cid, action="created"
    )
    linked = events.record(
        db_conn,
        actor_user_id=None,
        entity_type="revision",
        entity_id=str(uuid.uuid4()),
        action="uploaded",
        detail={"change_id": cid},
    )
    events.record(
        db_conn,
        actor_user_id=None,
        entity_type="revision",
        entity_id=str(uuid.uuid4()),
        action="other",
    )
    ids = {r["id"] for r in events.for_change(db_conn, cid)}
    assert ids == {direct["id"], linked["id"]}
