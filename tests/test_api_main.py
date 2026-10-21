import pytest

from api.main import app
from models.errors import LifecycleError


def test_health(api_client):
    r = api_client.client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_me_returns_user(api_client, seed_users):
    api_client.as_user("docmgr@example.test")
    r = api_client.client.get("/me")
    assert r.status_code == 200
    body = r.json()
    assert body["email"] == "docmgr@example.test"
    assert body["role"] == "engineering"
    assert body["is_doc_manager"] is True
    assert body["deactivated"] is False
    assert body["id"] == str(seed_users["docmgr"]["id"])


@pytest.mark.parametrize(
    ("code", "status"),
    [
        ("not_found", 404),
        ("forbidden", 403),
        ("self_approval", 403),
        ("not_an_approver", 403),
        ("wrong_status", 409),
        ("locked", 409),
        ("document_busy", 409),
        ("type_mismatch", 409),
        ("too_large", 413),
        ("invalid_file", 415),
        ("no_approvers", 422),
        ("no_revisions", 422),
        ("cutin_required", 422),
        ("comment_required", 422),
        ("something_new", 500),
    ],
)
def test_lifecycle_error_maps_to_status(api_client, code, status):
    path = f"/_boom/{code}"

    @app.get(path)
    def boom():
        raise LifecycleError(code, "x")

    try:
        r = api_client.client.get(path)
    finally:
        app.router.routes.pop()
    assert r.status_code == status
    assert r.json() == {"detail": code, "message": "x"}
