from collections.abc import Iterator

from clients import db, storage


def get_storage() -> storage.Storage:
    return storage.from_env()


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
