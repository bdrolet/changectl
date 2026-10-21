def test_select_one(raw_conn):
    assert raw_conn.execute("SELECT 1 AS one").fetchone() == {"one": 1}


def test_cloud_sql_connector_is_created_once_and_reused(monkeypatch):
    import google.cloud.sql.connector as connector_module

    from clients import db

    made = []

    class FakeConnector:
        def __init__(self):
            made.append(self)
            self.connects = 0

        def connect(self, *args, **kwargs):
            self.connects += 1
            return object()

    monkeypatch.setattr(connector_module, "Connector", FakeConnector)
    monkeypatch.setattr(db, "_connector", None)
    monkeypatch.setenv("POSTGRES_USER", "u")
    monkeypatch.setenv("POSTGRES_PASSWORD", "p")
    db._cloud_sql_conn("proj:region:inst")
    db._cloud_sql_conn("proj:region:inst")
    assert len(made) == 1
    assert made[0].connects == 2
