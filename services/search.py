"""Search over controlled documents: titles and the text of the current release."""

from typing import Any

from models.display import display_number
from repo import documents

_SELECT = """
    SELECT d.id AS document_id, d.title, d.current_revision_id, r.revision_number,
           r.released_at, u.name AS released_by_name, r.original_filename,
           {rank} AS rank
    FROM documents d
    JOIN revisions r ON r.id = d.current_revision_id
    LEFT JOIN users u ON u.id = r.released_by
"""

_ALL_SQL = (
    _SELECT.format(rank="0.0::float8")
    + """
    WHERE d.current_revision_id IS NOT NULL
    ORDER BY r.released_at DESC, d.title
    LIMIT %s::int
    """
)

_LEXEME_COUNT_SQL = "SELECT numnode(websearch_to_tsquery('english', %s::text)) AS n"

_FTS_SQL = (
    _SELECT.format(
        rank="""(ts_rank(d.title_search, websearch_to_tsquery('english', %s::text)) * 2
                + ts_rank(r.search, websearch_to_tsquery('english', %s::text)))::float8"""
    )
    + """
    WHERE d.current_revision_id IS NOT NULL
      AND (d.title_search @@ websearch_to_tsquery('english', %s::text)
           OR r.search @@ websearch_to_tsquery('english', %s::text))
    ORDER BY rank DESC, r.released_at DESC, d.title
    LIMIT %s::int
    """
)

_ILIKE_SQL = (
    _SELECT.format(rank="0.0::float8")
    + r"""
    WHERE d.current_revision_id IS NOT NULL
      AND d.title ILIKE '%%' || %s::text || '%%' ESCAPE '\'
    ORDER BY r.released_at DESC, d.title
    LIMIT %s::int
    """
)

_CHANGES_SQL = """
    SELECT id, number, title, status, cutin_date
    FROM changes WHERE id = ANY(%s::uuid[])
"""

_APPROVALS_SQL = """
    SELECT a.change_id, u.name, a.email, a.signed_at
    FROM approvals a JOIN users u ON u.id = a.user_id
    WHERE a.change_id = ANY(%s::uuid[]) AND a.voided_at IS NULL AND a.decision = 'approved'
    ORDER BY a.signed_at, a.id
"""


def _escape_like(q: str) -> str:
    return q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def search_documents(conn: Any, q: str, *, limit: int = 50) -> list[dict]:
    q = q.strip()
    if not q:
        return conn.execute(_ALL_SQL, (limit,)).fetchall()
    n = conn.execute(_LEXEME_COUNT_SQL, (q,)).fetchone()["n"]
    if n == 0:
        return conn.execute(_ILIKE_SQL, (_escape_like(q), limit)).fetchall()
    return conn.execute(_FTS_SQL, (q, q, q, q, limit)).fetchall()


def document_detail(conn: Any, document_id: str) -> dict | None:
    doc = documents.document(conn, document_id)
    if doc is None:
        return None
    revs = documents.revisions_for_document(conn, document_id)
    change_ids = list({str(r["change_id"]) for r in revs})
    meta = {str(c["id"]): c for c in conn.execute(_CHANGES_SQL, (change_ids,)).fetchall()}
    signed: dict[str, list[dict]] = {cid: [] for cid in change_ids}
    for a in conn.execute(_APPROVALS_SQL, (change_ids,)).fetchall():
        signed[str(a["change_id"])].append(
            {"name": a["name"], "email": a["email"], "signed_at": a["signed_at"]}
        )
    out = []
    for r in revs:
        cid = str(r["change_id"])
        c = meta[cid]
        out.append(
            {
                **r,
                "change_number": int(c["number"]),
                "change_display": display_number(int(c["number"])),
                "change_title": c["title"],
                "change_status": c["status"],
                "cutin_date": c["cutin_date"],
                "approvals": signed[cid],
            }
        )
    return {**doc, "revisions": out}
