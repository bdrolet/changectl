def test_select_one(raw_conn):
    assert raw_conn.execute("SELECT 1 AS one").fetchone() == {"one": 1}
