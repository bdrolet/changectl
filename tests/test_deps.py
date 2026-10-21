import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient

from api.deps import get_conn_dep


class StubConn:
    def __init__(self):
        self.calls: list[str] = []

    def commit(self):
        self.calls.append("commit")

    def rollback(self):
        self.calls.append("rollback")

    def close(self):
        self.calls.append("close")


@pytest.fixture
def client_and_conn(monkeypatch):
    conn = StubConn()
    monkeypatch.setattr("clients.db.get_conn", lambda: conn)
    app = FastAPI()

    @app.get("/ok")
    def ok(_=Depends(get_conn_dep)):
        return {"ok": True}

    @app.get("/conflict")
    def conflict(_=Depends(get_conn_dep)):
        raise HTTPException(409, detail="conflict")

    @app.get("/boom")
    def boom(_=Depends(get_conn_dep)):
        raise RuntimeError("boom")

    return TestClient(app, raise_server_exceptions=False), conn


def test_success_commits_and_closes(client_and_conn):
    client, conn = client_and_conn
    assert client.get("/ok").status_code == 200
    assert conn.calls == ["commit", "close"]


def test_http_exception_rolls_back_and_closes(client_and_conn):
    client, conn = client_and_conn
    assert client.get("/conflict").status_code == 409
    assert conn.calls == ["rollback", "close"]


def test_unexpected_error_rolls_back_closes_and_500(client_and_conn):
    client, conn = client_and_conn
    assert client.get("/boom").status_code == 500
    assert conn.calls == ["rollback", "close"]


def test_commit_happens_before_the_response_is_sent(monkeypatch):
    """Every route's connection must commit before the client sees the response."""
    conn = StubConn()
    monkeypatch.setattr("clients.db.get_conn", lambda: conn)
    app = FastAPI()

    @app.get("/write")
    def write(c=Depends(get_conn_dep, scope="function")):
        c.calls.append("handler")
        return {"ok": True}

    async def recording(scope, receive, send):
        async def wrapped(message):
            if message["type"] == "http.response.start":
                conn.calls.append("response")
            await send(message)

        await app(scope, receive, wrapped)

    assert TestClient(recording).get("/write").status_code == 200
    assert conn.calls == ["handler", "commit", "close", "response"]

    # Every get_conn_dep use in the real app is function-scoped, so one connection
    # is shared per request and committed before the response.
    from fastapi.routing import APIRoute

    from api.routers import audit, changes, documents, me, users

    def walk(dependant):
        for sub in dependant.dependencies:
            if sub.call is get_conn_dep:
                yield sub
            yield from walk(sub)

    found = [
        sub
        for module in (audit, changes, documents, me, users)
        for route in module.router.routes
        if isinstance(route, APIRoute)
        for sub in walk(route.dependant)
    ]
    assert found
    assert {sub.scope for sub in found} == {"function"}
