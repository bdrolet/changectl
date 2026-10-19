import json
from typing import Any

_STAMP = {"approval": "submitted_at", "implementation": "approved_at", "closed": "closed_at"}


def insert(
    conn: Any,
    *,
    title: str,
    description: str,
    reason: str,
    justification: str,
    created_by: str,
) -> dict:
    return conn.execute(
        """
        INSERT INTO changes (title, description, reason, justification, created_by)
        VALUES (%s, %s, %s, %s, %s::uuid)
        RETURNING *
        """,
        (title, description, reason, justification, created_by),
    ).fetchone()


def lock(conn: Any, change_id: str) -> None:
    """Row-lock the change until the caller's transaction ends."""
    conn.execute("SELECT id FROM changes WHERE id = %s::uuid FOR UPDATE", (change_id,))


def get(conn: Any, change_id: str) -> dict | None:
    return conn.execute("SELECT * FROM changes WHERE id = %s::uuid", (change_id,)).fetchone()


def list_by_status(conn: Any, status: str | None) -> list[dict]:
    if status is None:
        return conn.execute("SELECT * FROM changes ORDER BY created_at DESC, id").fetchall()
    return conn.execute(
        "SELECT * FROM changes WHERE status = %s::change_status ORDER BY created_at DESC, id",
        (status,),
    ).fetchall()


def update_fields(
    conn: Any,
    change_id: str,
    *,
    title: str | None = None,
    description: str | None = None,
    reason: str | None = None,
    justification: str | None = None,
) -> dict:
    return conn.execute(
        """
        UPDATE changes
        SET title = COALESCE(%s, title),
            description = COALESCE(%s, description),
            reason = COALESCE(%s, reason),
            justification = COALESCE(%s, justification)
        WHERE id = %s::uuid
        RETURNING *
        """,
        (title, description, reason, justification, change_id),
    ).fetchone()


def set_status(conn: Any, change_id: str, status: str, *, at: Any) -> dict:
    column = _STAMP.get(status)
    if column is None:
        return conn.execute(
            "UPDATE changes SET status = %s::change_status WHERE id = %s::uuid RETURNING *",
            (status, change_id),
        ).fetchone()
    return conn.execute(
        f"UPDATE changes SET status = %s::change_status, {column} = %s::timestamptz "
        "WHERE id = %s::uuid RETURNING *",
        (status, at, change_id),
    ).fetchone()


def set_cutin(conn: Any, change_id: str, cutin_date: Any) -> None:
    conn.execute(
        "UPDATE changes SET cutin_date = %s::date WHERE id = %s::uuid", (cutin_date, change_id)
    )


def link_revision(conn: Any, change_id: str, revision_id: str) -> None:
    conn.execute(
        """
        INSERT INTO change_revisions (change_id, revision_id)
        VALUES (%s::uuid, %s::uuid)
        ON CONFLICT DO NOTHING
        """,
        (change_id, revision_id),
    )


def unlink_revision(conn: Any, change_id: str, revision_id: str) -> None:
    conn.execute(
        "DELETE FROM change_revisions WHERE change_id = %s::uuid AND revision_id = %s::uuid",
        (change_id, revision_id),
    )


def set_approvers(conn: Any, change_id: str, user_ids: list[str], added_by: str) -> None:
    conn.execute("DELETE FROM approvers WHERE change_id = %s::uuid", (change_id,))
    for user_id in user_ids:
        conn.execute(
            """
            INSERT INTO approvers (change_id, user_id, added_by)
            VALUES (%s::uuid, %s::uuid, %s::uuid)
            """,
            (change_id, user_id, added_by),
        )


def approvers(conn: Any, change_id: str) -> list[dict]:
    return conn.execute(
        """
        SELECT a.user_id, u.name, u.email, u.role, a.added_at
        FROM approvers a JOIN users u ON u.id = a.user_id
        WHERE a.change_id = %s::uuid
        ORDER BY a.added_at, a.user_id
        """,
        (change_id,),
    ).fetchall()


def insert_approval(
    conn: Any,
    *,
    change_id: str,
    user_id: str,
    google_sub: str,
    email: str,
    decision: str,
    comment: str | None,
    file_sha256s: list[str],
) -> dict:
    return conn.execute(
        """
        INSERT INTO approvals (change_id, user_id, google_sub, email, decision, comment,
                               file_sha256s)
        VALUES (%s::uuid, %s::uuid, %s, %s, %s::approval_decision, %s, %s::jsonb)
        RETURNING *
        """,
        (change_id, user_id, google_sub, email, decision, comment, json.dumps(file_sha256s)),
    ).fetchone()


def live_approvals(conn: Any, change_id: str) -> list[dict]:
    return conn.execute(
        """
        SELECT * FROM approvals
        WHERE change_id = %s::uuid AND voided_at IS NULL
        ORDER BY signed_at, id
        """,
        (change_id,),
    ).fetchall()


def void_approvals(conn: Any, change_id: str, reason: str, at: Any) -> int:
    cur = conn.execute(
        """
        UPDATE approvals SET voided_at = %s::timestamptz, voided_reason = %s
        WHERE change_id = %s::uuid AND voided_at IS NULL
        """,
        (at, reason, change_id),
    )
    return cur.rowcount


def insert_comment(conn: Any, *, change_id: str, user_id: str, body: str) -> dict:
    return conn.execute(
        """
        INSERT INTO comments (change_id, user_id, body, created_at)
        VALUES (%s::uuid, %s::uuid, %s, clock_timestamp())
        RETURNING *
        """,
        (change_id, user_id, body),
    ).fetchone()


def comments(conn: Any, change_id: str) -> list[dict]:
    return conn.execute(
        "SELECT * FROM comments WHERE change_id = %s::uuid ORDER BY created_at, id",
        (change_id,),
    ).fetchall()


def open_changes_awaiting(conn: Any, user_id: str) -> list[dict]:
    return conn.execute(
        """
        SELECT c.* FROM changes c
        JOIN approvers a ON a.change_id = c.id AND a.user_id = %s::uuid
        WHERE c.status = 'approval'
          AND NOT EXISTS (
              SELECT 1 FROM approvals p
              WHERE p.change_id = c.id AND p.user_id = a.user_id
                AND p.decision = 'approved' AND p.voided_at IS NULL
          )
        ORDER BY c.number
        """,
        (user_id,),
    ).fetchall()


def all_approvals(conn: Any, change_id: str) -> list[dict]:
    """Every approval row, live and voided, newest first, with the signer's name."""
    return conn.execute(
        """
        SELECT p.*, u.name
        FROM approvals p JOIN users u ON u.id = p.user_id
        WHERE p.change_id = %s::uuid
        ORDER BY p.signed_at DESC, p.id
        """,
        (change_id,),
    ).fetchall()


def comments_with_names(conn: Any, change_id: str) -> list[dict]:
    return conn.execute(
        """
        SELECT c.*, u.name
        FROM comments c JOIN users u ON u.id = c.user_id
        WHERE c.change_id = %s::uuid
        ORDER BY c.created_at, c.id
        """,
        (change_id,),
    ).fetchall()
