from typing import Any


def insert(
    conn: Any,
    *,
    email: str,
    name: str,
    role: str,
    is_doc_manager: bool,
    invited_by: str | None,
) -> dict:
    return conn.execute(
        """
        INSERT INTO users (email, name, role, is_doc_manager, invited_by)
        VALUES (%s, %s, %s::user_role, %s, %s::uuid)
        RETURNING *
        """,
        (email.lower(), name, role, is_doc_manager, invited_by),
    ).fetchone()


def by_email(conn: Any, email: str) -> dict | None:
    return conn.execute("SELECT * FROM users WHERE email = %s", (email.lower(),)).fetchone()


def by_id(conn: Any, user_id: str) -> dict | None:
    return conn.execute("SELECT * FROM users WHERE id = %s::uuid", (user_id,)).fetchone()


def list_all(conn: Any) -> list[dict]:
    return conn.execute("SELECT * FROM users ORDER BY created_at, email").fetchall()


def set_google_sub(conn: Any, user_id: str, sub: str) -> None:
    conn.execute("UPDATE users SET google_sub = %s WHERE id = %s::uuid", (sub, user_id))


def update(
    conn: Any,
    user_id: str,
    *,
    role: str | None = None,
    is_doc_manager: bool | None = None,
    deactivated: bool | None = None,
) -> dict:
    sets: list[str] = []
    params: list[Any] = []
    if role is not None:
        sets.append("role = %s::user_role")
        params.append(role)
    if is_doc_manager is not None:
        sets.append("is_doc_manager = %s")
        params.append(is_doc_manager)
    if deactivated is True:
        sets.append("deactivated_at = COALESCE(deactivated_at, now())")
    elif deactivated is False:
        sets.append("deactivated_at = NULL")
    if not sets:
        return conn.execute("SELECT * FROM users WHERE id = %s::uuid", (user_id,)).fetchone()
    params.append(user_id)
    return conn.execute(
        f"UPDATE users SET {', '.join(sets)} WHERE id = %s::uuid RETURNING *",
        tuple(params),
    ).fetchone()
