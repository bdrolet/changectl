"""Seed a demo company: three released documents and one change mid-approval.

The open change's approvers are Marcus (a persona, already signed) and one live
account that can sign in during the demo: the second account when
SEED_SECOND_EMAIL is set, otherwise Tesa.

Needs SEED_TESA_EMAIL and SEED_BEN_EMAIL (optional SEED_SECOND_EMAIL) in the
environment, plus the usual POSTGRES_* / CHANGECTL_BUCKET settings. Safe to run
twice: a change whose title already exists is skipped.
"""

import os
import sys
from datetime import date
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import demo_files  # noqa: E402

from clients.storage import Storage  # noqa: E402
from models.display import display_number  # noqa: E402
from repo import users  # noqa: E402
from services import lifecycle  # noqa: E402

# Personas are history only: they never sign in, so their approvals carry a
# synthetic subject. The open change's pending approver is always a live account.
PERSONAS = {
    "Priya": ("priya@demo.example", "engineering"),
    "Marcus": ("marcus@demo.example", "operations"),
    "Dana": ("dana@demo.example", "quality"),
}

BOM_TITLE = "Prototype BOM"
OPEN_CHANGE = "Replace EOL connector J4"


def _ensure_user(
    conn: Any, email: str, name: str, role: str, doc_manager: bool = False
) -> tuple[dict, bool]:
    existing = users.by_email(conn, email)
    if existing is not None:
        return existing, False
    row = users.insert(
        conn, email=email, name=name, role=role, is_doc_manager=doc_manager, invited_by=None
    )
    return row, True


def _change_exists(conn: Any, title: str) -> bool:
    return conn.execute("SELECT 1 FROM changes WHERE title = %s", (title,)).fetchone() is not None


def _document_id(conn: Any, title: str) -> str:
    row = conn.execute("SELECT id FROM documents WHERE title = %s", (title,)).fetchone()
    return str(row["id"])


def _release_initial(
    conn: Any,
    storage: Storage,
    *,
    title: str,
    doc_title: str,
    filename: str,
    data: bytes,
    description: str,
    ben: dict,
    approvers: list[dict],
) -> dict:
    change = lifecycle.create_change(
        conn,
        ben,
        title=title,
        description=description,
        reason="Bring the document under change control.",
        justification="Initial release; no prior revision exists.",
    )
    cid = str(change["id"])
    lifecycle.attach_revision(
        conn, ben, cid, filename=filename, data=data, storage=storage, title=doc_title
    )
    lifecycle.set_approvers(conn, ben, cid, [str(a["id"]) for a in approvers])
    lifecycle.submit(conn, ben, cid)
    for a in approvers:
        lifecycle.approve(
            conn, a, cid, google_sub=f"seed:{a['name']}", comment="Reviewed, no concerns."
        )
    lifecycle.release(conn, ben, cid, cutin_date=date.today())
    return change


def main(conn: Any = None, storage: Storage | None = None) -> dict[str, int]:
    tesa_email = os.environ.get("SEED_TESA_EMAIL")
    ben_email = os.environ.get("SEED_BEN_EMAIL")
    second_email = os.environ.get("SEED_SECOND_EMAIL")
    if not tesa_email or not ben_email:
        print(
            "SEED_TESA_EMAIL and SEED_BEN_EMAIL must be set (SEED_SECOND_EMAIL is optional)",
            file=sys.stderr,
        )
        sys.exit(2)

    own_conn = conn is None
    if own_conn:
        from clients.db import get_conn

        conn = get_conn()
    if storage is None:
        from clients.storage import from_env

        storage = from_env()

    created: list[dict] = []
    try:
        tesa, _ = _ensure_user(conn, tesa_email, "Tesa", "quality", True)
        ben, _ = _ensure_user(conn, ben_email, "Ben", "engineering", True)
        live_approver = tesa
        if second_email:
            live_approver, _ = _ensure_user(conn, second_email, "Second account", "operations")
        people = {
            name: _ensure_user(conn, email, name, role)[0]
            for name, (email, role) in PERSONAS.items()
        }
        priya, marcus, dana = people["Priya"], people["Marcus"], people["Dana"]

        initial = [
            (
                "Initial release of prototype BOM",
                BOM_TITLE,
                "Prototype BOM.xlsx",
                demo_files.bom_xlsx(1),
                "First release of the prototype bill of materials.",
            ),
            (
                "Initial release of cable assembly spec",
                "Cable Assembly Spec",
                "Cable Assembly Spec.docx",
                demo_files.cable_spec_docx(),
                "First release of the cable assembly specification.",
            ),
            (
                "Initial release of connector supplier spec",
                "Supplier Spec - Connector",
                "Supplier Spec - Connector.pdf",
                demo_files.connector_spec_pdf(),
                "First release of the connector supplier specification.",
            ),
        ]
        for title, doc_title, filename, data, description in initial:
            if _change_exists(conn, title):
                continue
            created.append(
                _release_initial(
                    conn,
                    storage,
                    title=title,
                    doc_title=doc_title,
                    filename=filename,
                    data=data,
                    description=description,
                    ben=ben,
                    approvers=[priya, dana],
                )
            )

        if not _change_exists(conn, OPEN_CHANGE):
            change = lifecycle.create_change(
                conn,
                priya,
                title=OPEN_CHANGE,
                description="Connector J4 is end-of-life; move to an in-production equivalent.",
                reason="Northgate Connectors has announced end-of-life for the J4 part.",
                justification="Avoids a build stop; the replacement is form, fit and function "
                "equivalent.",
            )
            cid = str(change["id"])
            lifecycle.attach_revision(
                conn,
                priya,
                cid,
                filename="Prototype BOM rev2 redline.xlsx",
                data=demo_files.bom_xlsx(2),
                storage=storage,
                document_id=_document_id(conn, BOM_TITLE),
            )
            lifecycle.set_approvers(conn, priya, cid, [str(marcus["id"]), str(live_approver["id"])])
            lifecycle.submit(conn, priya, cid)
            lifecycle.approve(
                conn, marcus, cid, google_sub="seed:Marcus", comment="Supply confirmed."
            )
            created.append(change)

        if own_conn:
            conn.commit()

        counts = {
            "users": conn.execute("SELECT count(*) AS n FROM users").fetchone()["n"],
            "documents": conn.execute(
                "SELECT count(*) AS n FROM documents WHERE current_revision_id IS NOT NULL"
            ).fetchone()["n"],
            "changes": conn.execute("SELECT count(*) AS n FROM changes").fetchone()["n"],
        }
    except Exception:
        if own_conn:
            conn.rollback()
        raise
    finally:
        if own_conn:
            conn.close()

    for c in created:
        print(f"created {display_number(c['number'])} {c['title']}")
    if not created:
        print("nothing to do; demo data already present")
    return counts


if __name__ == "__main__":
    main()
