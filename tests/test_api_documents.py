import io
import uuid

import openpyxl

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _xlsx(word: str) -> bytes:
    wb = openpyxl.Workbook()
    wb.active["A1"] = word
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _release(api_client, seed_users, word: str = "Zirconium") -> tuple[str, str]:
    """Drive one change through to release; return (change_id, revision_id)."""
    c = api_client.client
    api_client.as_user("creator@example.test")
    r = c.post(
        "/changes",
        json={"title": "Swap valve", "description": "d", "reason": "r", "justification": "j"},
    )
    cid = r.json()["id"]
    r = c.post(
        f"/changes/{cid}/revisions",
        files={"file": ("../proc 1.xlsx", _xlsx(word), XLSX)},
        data={"title": "Procedure"},
    )
    assert r.status_code == 201, r.text
    rid = r.json()["id"]
    ids = [str(seed_users["quality"]["id"])]
    assert c.put(f"/changes/{cid}/approvers", json={"user_ids": ids}).status_code == 200
    assert c.post(f"/changes/{cid}/submit").status_code == 200
    api_client.as_user("quality@example.test")
    assert c.post(f"/changes/{cid}/approve", json={}).status_code == 200
    api_client.as_user("docmgr@example.test")
    r = c.post(f"/changes/{cid}/release", json={"cutin_date": "2026-11-01"})
    assert r.status_code == 200, r.text
    return cid, rid


def test_search_endpoint_finds_released_text(api_client, seed_users):
    cid, rid = _release(api_client, seed_users)
    c = api_client.client
    hits = c.get("/documents", params={"q": "Zirconium"}).json()
    assert [h["title"] for h in hits] == ["Procedure"]
    assert hits[0]["current_revision_id"] == rid
    assert hits[0]["rank"] > 0
    assert c.get("/documents", params={"q": "nonexistentword"}).json() == []
    assert len(c.get("/documents").json()) == 1

    detail = c.get(f"/documents/{hits[0]['id']}").json()
    assert detail["revisions"][0]["change_id"] == cid
    assert detail["revisions"][0]["change_number"].startswith("CHG-")
    assert detail["revisions"][0]["approvals"][0]["name"] == "Quality"
    assert c.get(f"/documents/{uuid.uuid4()}").status_code == 404
    assert c.get("/documents/not-a-uuid").status_code == 404


def test_download_redirects_and_logs_event(api_client, seed_users, db_conn):
    cid, rid = _release(api_client, seed_users)
    c = api_client.client
    r = c.get(f"/revisions/{rid}/download", follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"].startswith("file://")
    row = db_conn.execute(
        "SELECT detail FROM events WHERE action = 'revision.downloaded' AND entity_id = %s::uuid",
        (rid,),
    ).fetchone()
    assert row["detail"] == {"change_id": cid, "which": "released"}
    assert c.get(f"/revisions/{rid}/download?which=bogus").status_code == 422
    assert c.get(f"/revisions/{uuid.uuid4()}/download").status_code == 404


def test_download_passes_sanitised_filename(api_client, seed_users):
    from api.deps import get_storage
    from api.main import app

    seen = []

    class Spy:
        def signed_url(self, key, filename, minutes=10):
            seen.append(filename)
            return "file:///x"

    _, rid = _release(api_client, seed_users)
    app.dependency_overrides[get_storage] = lambda: Spy()
    r = api_client.client.get(f"/revisions/{rid}/download", follow_redirects=False)
    assert r.status_code == 302
    assert seen == [".._proc_1.xlsx"]


def test_download_redline_404_when_absent(api_client, seed_users):
    _, rid = _release(api_client, seed_users)
    r = api_client.client.get(f"/revisions/{rid}/download?which=redline", follow_redirects=False)
    assert r.status_code == 404
    assert r.json()["detail"] == "not_found"


def test_audit_requires_both_params(api_client, seed_users):
    cid, _ = _release(api_client, seed_users)
    c = api_client.client
    assert c.get("/audit").status_code == 422
    assert c.get("/audit", params={"entity_type": "change"}).status_code == 422
    assert c.get("/audit", params={"entity_id": cid}).status_code == 422
    assert c.get("/audit", params={"entity_type": "bogus", "entity_id": cid}).status_code == 422
    r = c.get("/audit", params={"entity_type": "change", "entity_id": cid})
    assert r.status_code == 200
    assert r.json() and all(e["entity_id"] == cid for e in r.json())
    assert any(e["actor_name"] for e in r.json())
    assert c.get("/audit", params={"entity_type": "change", "entity_id": "zzz"}).status_code == 404
