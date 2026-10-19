import pytest
from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient

from api import auth
from api.deps import get_conn_dep
from clients.google_id_token import Claims
from repo import events, users


@pytest.fixture
def ctx(db_conn, monkeypatch):
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "client-id")
    monkeypatch.delenv("K_SERVICE", raising=False)
    monkeypatch.delenv("CHANGECTL_DEV_USER_EMAIL", raising=False)

    state: dict = {"claims": Claims("sub-1", "ann@example.com", True, "Ann"), "calls": []}

    def fake_verify(token, audience):
        state["calls"].append((token, audience))
        c = state["claims"]
        if isinstance(c, Exception):
            raise c
        return c

    monkeypatch.setattr("api.auth.verify_id_token", fake_verify)

    app = FastAPI()

    @app.get("/me")
    def me(request: Request, user: dict = Depends(auth.current_user)):
        return {"email": user["email"], "sub": request.state.google_sub}

    @app.get("/dm")
    def dm(user: dict = Depends(auth.require_doc_manager)):
        return {"email": user["email"]}

    app.dependency_overrides[get_conn_dep] = lambda: db_conn
    state["client"] = TestClient(app)
    state["conn"] = db_conn
    return state


def _user(conn, email="ann@example.com", dm=False):
    row = users.insert(
        conn, email=email, name="Ann", role="engineering", is_doc_manager=dm, invited_by=None
    )
    conn.commit()
    return row


H = {"Authorization": "Bearer tok"}


def test_missing_bearer_401(ctx):
    for headers in ({}, {"Authorization": "Basic abc"}, {"Authorization": "Bearer"}):
        r = ctx["client"].get("/me", headers=headers)
        assert r.status_code == 401
        assert r.json() == {"detail": "missing_bearer"}


def test_bad_token_401(ctx):
    ctx["claims"] = ValueError("bad")
    r = ctx["client"].get("/me", headers=H)
    assert r.status_code == 401
    assert r.json() == {"detail": "invalid_token"}


def test_unverified_email_401(ctx):
    _user(ctx["conn"])
    ctx["claims"] = Claims("sub-1", "ann@example.com", False, None)
    r = ctx["client"].get("/me", headers=H)
    assert r.status_code == 401
    assert r.json() == {"detail": "email_unverified"}


def test_unknown_email_403_not_invited(ctx):
    r = ctx["client"].get("/me", headers=H)
    assert r.status_code == 403
    assert r.json() == {"detail": "not_invited"}


def test_deactivated_403(ctx):
    row = _user(ctx["conn"])
    users.update(ctx["conn"], str(row["id"]), deactivated=True)
    r = ctx["client"].get("/me", headers=H)
    assert r.status_code == 403
    assert r.json() == {"detail": "not_invited"}


def test_first_sign_in_stores_sub_and_event(ctx):
    row = _user(ctx["conn"])
    r = ctx["client"].get("/me", headers=H)
    assert r.status_code == 200
    assert r.json() == {"email": "ann@example.com", "sub": "sub-1"}
    assert ctx["calls"] == [("tok", "client-id")]
    assert users.by_id(ctx["conn"], str(row["id"]))["google_sub"] == "sub-1"
    evs = events.for_entity(ctx["conn"], "user", str(row["id"]))
    assert [e["action"] for e in evs] == ["user.first_sign_in"]
    assert evs[0]["detail"] == {"email": "ann@example.com"}
    # second sign-in does not record another event
    assert ctx["client"].get("/me", headers=H).status_code == 200
    assert len(events.for_entity(ctx["conn"], "user", str(row["id"]))) == 1


def test_sub_mismatch_403(ctx):
    row = _user(ctx["conn"])
    users.set_google_sub(ctx["conn"], str(row["id"]), "other-sub")
    r = ctx["client"].get("/me", headers=H)
    assert r.status_code == 403
    assert r.json() == {"detail": "identity_mismatch"}


def test_dev_bypass_only_off_cloud_run(ctx, monkeypatch):
    _user(ctx["conn"])
    monkeypatch.setenv("CHANGECTL_DEV_USER_EMAIL", "ann@example.com")
    r = ctx["client"].get("/me")  # no Authorization header
    assert r.status_code == 200
    assert r.json() == {"email": "ann@example.com", "sub": "dev"}
    assert ctx["calls"] == []
    monkeypatch.setenv("K_SERVICE", "changectl-api")
    r = ctx["client"].get("/me")
    assert r.status_code == 401
    assert r.json() == {"detail": "missing_bearer"}
    assert ctx["calls"] == []


def test_dev_bypass_unknown_email_403(ctx, monkeypatch):
    monkeypatch.setenv("CHANGECTL_DEV_USER_EMAIL", "nobody@example.com")
    r = ctx["client"].get("/me")
    assert r.status_code == 403
    assert r.json() == {"detail": "not_invited"}


def test_require_doc_manager(ctx):
    _user(ctx["conn"])
    r = ctx["client"].get("/dm", headers=H)
    assert r.status_code == 403
    assert r.json() == {"detail": "doc_manager_required"}
    users.update(
        ctx["conn"], str(users.by_email(ctx["conn"], "ann@example.com")["id"]), is_doc_manager=True
    )
    assert ctx["client"].get("/dm", headers=H).status_code == 200
