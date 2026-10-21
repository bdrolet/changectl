import io

import openpyxl

from services import lifecycle

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _xlsx() -> bytes:
    wb = openpyxl.Workbook()
    wb.active["A1"] = "Part"
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _create(c) -> str:
    r = c.post(
        "/changes",
        json={"title": "Swap valve", "description": "d", "reason": "r", "justification": "j"},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _upload(c, cid: str, data: bytes | None = None, name: str = "proc.xlsx", ctype: str = XLSX):
    return c.post(
        f"/changes/{cid}/revisions",
        files={"file": (name, data if data is not None else _xlsx(), ctype)},
        data={"title": "Procedure"},
    )


def _submitted(api_client, seed_users) -> str:
    api_client.as_user("creator@example.test")
    c = api_client.client
    cid = _create(c)
    assert _upload(c, cid).status_code == 201
    ids = [str(seed_users["quality"]["id"]), str(seed_users["ops"]["id"])]
    r = c.put(f"/changes/{cid}/approvers", json={"user_ids": ids})
    assert r.status_code == 200, r.text
    r = c.post(f"/changes/{cid}/submit")
    assert r.status_code == 200, r.text
    return cid


def test_initial_release_via_api(api_client, seed_users):
    c = api_client.client
    cid = _submitted(api_client, seed_users)
    detail = c.get(f"/changes/{cid}").json()
    assert detail["status"] == "approval"
    assert detail["number"].startswith("CHG-")
    assert sorted(detail["waiting_on"]) == ["Ops", "Quality"]
    assert detail["documents"] == ["Procedure"]

    api_client.as_user("quality@example.test")
    r = c.post(f"/changes/{cid}/approve", json={"comment": "ok"})
    assert r.status_code == 200, r.text
    assert r.json()["waiting_on"] == ["Ops"]
    api_client.as_user("ops@example.test")
    r = c.post(f"/changes/{cid}/approve")  # no body at all
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "implementation"
    assert r.json()["waiting_on"] == []

    api_client.as_user("docmgr@example.test")
    assert c.post(f"/changes/{cid}/release", json={}).status_code == 422
    r = c.post(f"/changes/{cid}/release", json={"cutin_date": "2026-11-01"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "closed"
    assert body["cutin_date"] == "2026-11-01"
    assert body["revisions"][0]["revision_number"] == 1
    assert len(body["approvals"]) == 2
    assert body["events"]


def test_upload_renamed_exe_as_pdf_415(api_client, seed_users):
    api_client.as_user("creator@example.test")
    c = api_client.client
    cid = _create(c)
    r = _upload(c, cid, data=b"MZ" + b"\x00" * 200, name="x.pdf", ctype="application/pdf")
    assert r.status_code == 415
    assert c.get(f"/changes/{cid}").json()["revisions"] == []


def test_upload_over_cap_413(api_client, seed_users, monkeypatch):
    monkeypatch.setattr(lifecycle, "MAX_UPLOAD_BYTES", 10)
    api_client.as_user("creator@example.test")
    c = api_client.client
    cid = _create(c)
    assert _upload(c, cid).status_code == 413


def test_approver_state_fields(api_client, seed_users):
    c = api_client.client
    cid = _submitted(api_client, seed_users)

    def states():
        return {a["name"]: a["state"] for a in c.get(f"/changes/{cid}").json()["approvers"]}

    assert states() == {"Quality": "pending", "Ops": "pending"}
    api_client.as_user("quality@example.test")
    assert c.post(f"/changes/{cid}/approve", json={}).status_code == 200
    assert states() == {"Quality": "signed", "Ops": "pending"}
    api_client.as_user("ops@example.test")
    r = c.post(f"/changes/{cid}/request-changes", json={"comment": "fix"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "initiate"
    assert states() == {"Quality": "pending", "Ops": "changes_requested"}


def test_release_requires_cutin_422(api_client, seed_users):
    c = api_client.client
    cid = _submitted(api_client, seed_users)
    for who in ("quality", "ops"):
        api_client.as_user(f"{who}@example.test")
        c.post(f"/changes/{cid}/approve", json={})
    api_client.as_user("docmgr@example.test")
    r = c.post(f"/changes/{cid}/release", json={})
    assert r.status_code == 422
    assert r.json()["detail"] == "cutin_required"
    assert c.get(f"/changes/{cid}").json()["status"] == "implementation"


def test_next_revision_number_and_superseded(api_client, seed_users):
    c = api_client.client
    cid = _submitted(api_client, seed_users)
    rev = c.get(f"/changes/{cid}").json()["revisions"][0]
    assert rev["next_revision_number"] == 1
    assert rev["superseded_at"] is None

    api_client.as_user("quality@example.test")
    assert c.post(f"/changes/{cid}/approve", json={}).status_code == 200
    api_client.as_user("ops@example.test")
    assert c.post(f"/changes/{cid}/approve").status_code == 200
    api_client.as_user("docmgr@example.test")
    r = c.post(f"/changes/{cid}/release", json={"cutin_date": "2026-11-01"})
    assert r.status_code == 200, r.text
    released = r.json()["revisions"][0]
    assert released["revision_number"] == 1
    assert released["next_revision_number"] is None

    api_client.as_user("creator@example.test")
    cid2 = _create(c)
    r = c.post(
        f"/changes/{cid2}/revisions",
        files={"file": ("proc.xlsx", _xlsx(), XLSX)},
        data={"document_id": released["document_id"]},
    )
    assert r.status_code == 201, r.text
    assert r.json()["next_revision_number"] == 2
    detail = c.get(f"/changes/{cid2}").json()
    assert detail["revisions"][0]["next_revision_number"] == 2
