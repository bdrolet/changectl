from typing import Any

_REV_WITH_CHANGE = """
    SELECT r.*, c.number AS change_number, c.status AS change_status
    FROM revisions r
    JOIN changes c ON c.id = r.change_id
"""


def insert_document(conn: Any, *, title: str, created_by: str) -> dict:
    return conn.execute(
        "INSERT INTO documents (title, created_by) VALUES (%s, %s::uuid) RETURNING *",
        (title, created_by),
    ).fetchone()


def document(conn: Any, document_id: str) -> dict | None:
    return conn.execute("SELECT * FROM documents WHERE id = %s::uuid", (document_id,)).fetchone()


def insert_revision(
    conn: Any,
    *,
    document_id: str,
    change_id: str,
    original_filename: str,
    content_type: str,
    byte_size: int,
    sha256: str,
    gcs_key: str,
    extracted_text: str | None,
    uploaded_by: str,
) -> dict:
    return conn.execute(
        """
        INSERT INTO revisions (document_id, change_id, original_filename, content_type,
                               byte_size, sha256, gcs_key, extracted_text, uploaded_by)
        VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s, %s::uuid)
        RETURNING *
        """,
        (
            document_id,
            change_id,
            original_filename,
            content_type,
            byte_size,
            sha256,
            gcs_key,
            extracted_text,
            uploaded_by,
        ),
    ).fetchone()


def lock(conn: Any, document_id: str) -> None:
    """Row-lock the document until the caller's transaction ends."""
    conn.execute("SELECT id FROM documents WHERE id = %s::uuid FOR UPDATE", (document_id,))


def delete_document(conn: Any, document_id: str) -> None:
    conn.execute("DELETE FROM documents WHERE id = %s::uuid", (document_id,))


def set_gcs_key(conn: Any, revision_id: str, gcs_key: str) -> None:
    conn.execute("UPDATE revisions SET gcs_key = %s WHERE id = %s::uuid", (gcs_key, revision_id))


def revision(conn: Any, revision_id: str) -> dict | None:
    return conn.execute("SELECT * FROM revisions WHERE id = %s::uuid", (revision_id,)).fetchone()


def revisions_for_document(conn: Any, document_id: str) -> list[dict]:
    return conn.execute(
        _REV_WITH_CHANGE
        + """
        WHERE r.document_id = %s::uuid
        ORDER BY r.revision_number DESC NULLS FIRST, r.uploaded_at DESC
        """,
        (document_id,),
    ).fetchall()


def revisions_for_change(conn: Any, change_id: str) -> list[dict]:
    return conn.execute(
        _REV_WITH_CHANGE
        + """
        WHERE r.change_id = %s::uuid
        ORDER BY r.uploaded_at, r.id
        """,
        (change_id,),
    ).fetchall()


def delete_revision(conn: Any, revision_id: str) -> None:
    conn.execute("DELETE FROM change_revisions WHERE revision_id = %s::uuid", (revision_id,))
    conn.execute("DELETE FROM revisions WHERE id = %s::uuid", (revision_id,))


def set_release_file(
    conn: Any,
    revision_id: str,
    *,
    gcs_key: str,
    sha256: str,
    content_type: str,
    byte_size: int,
    original_filename: str,
    extracted_text: str | None,
    redline_gcs_key: str,
    redline_sha256: str,
) -> dict:
    return conn.execute(
        """
        UPDATE revisions
        SET gcs_key = %s, sha256 = %s, content_type = %s, byte_size = %s,
            original_filename = %s, extracted_text = %s,
            redline_gcs_key = %s, redline_sha256 = %s
        WHERE id = %s::uuid
        RETURNING *
        """,
        (
            gcs_key,
            sha256,
            content_type,
            byte_size,
            original_filename,
            extracted_text,
            redline_gcs_key,
            redline_sha256,
            revision_id,
        ),
    ).fetchone()


def release(
    conn: Any,
    revision_id: str,
    *,
    revision_number: int,
    released_by: str,
    released_at: Any,
) -> dict:
    return conn.execute(
        """
        UPDATE revisions
        SET revision_number = %s, released_by = %s::uuid, released_at = %s::timestamptz
        WHERE id = %s::uuid
        RETURNING *
        """,
        (revision_number, released_by, released_at, revision_id),
    ).fetchone()


def supersede_current(conn: Any, document_id: str, new_revision_id: str, at: Any) -> None:
    conn.execute(
        """
        UPDATE revisions SET superseded_at = %s::timestamptz
        WHERE id = (SELECT current_revision_id FROM documents WHERE id = %s::uuid)
        """,
        (at, document_id),
    )
    conn.execute(
        "UPDATE documents SET current_revision_id = %s::uuid WHERE id = %s::uuid",
        (new_revision_id, document_id),
    )


def next_revision_number(conn: Any, document_id: str) -> int:
    row = conn.execute(
        """
        SELECT COALESCE(MAX(revision_number), 0) + 1 AS n
        FROM revisions WHERE document_id = %s::uuid AND released_at IS NOT NULL
        """,
        (document_id,),
    ).fetchone()
    return int(row["n"])


def pending_revision_exists(conn: Any, document_id: str) -> bool:
    row = conn.execute(
        """
        SELECT EXISTS (
            SELECT 1 FROM revisions r JOIN changes c ON c.id = r.change_id
            WHERE r.document_id = %s::uuid AND r.released_at IS NULL AND c.status <> 'closed'
        ) AS e
        """,
        (document_id,),
    ).fetchone()
    return bool(row["e"])
