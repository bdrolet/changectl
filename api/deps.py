from collections.abc import Iterator

from clients import db

# get_storage will also live here.


def get_conn_dep() -> Iterator:
    conn = db.get_conn()
    try:
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()
