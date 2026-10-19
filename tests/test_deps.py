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
