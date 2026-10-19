"""Build the API's change views from repo rows. Read-only; no business rules."""

from typing import Any

from api.schemas import (
    ApprovalOut,
    ApproverOut,
    ChangeDetail,
    ChangeSummary,
    CommentOut,
    DocumentDetail,
    DocumentRevisionOut,
    DocumentSummary,
    EventOut,
    RevisionOut,
)
from models.display import display_number
from repo import changes, documents, events, users


def revision_out(conn: Any, row: dict) -> RevisionOut:
    doc = documents.document(conn, str(row["document_id"]))
    return RevisionOut(
        id=str(row["id"]),
        document_id=str(row["document_id"]),
        document_title=doc["title"] if doc else "",
        revision_number=row["revision_number"],
        original_filename=row["original_filename"],
        content_type=row["content_type"],
        byte_size=row["byte_size"],
        sha256=row["sha256"],
        has_redline=row["redline_gcs_key"] is not None,
        uploaded_by=str(row["uploaded_by"]),
        uploaded_at=row["uploaded_at"],
        released_at=row["released_at"],
    )


def comment_out(conn: Any, row: dict) -> CommentOut:
    user = users.by_id(conn, str(row["user_id"]))
    return CommentOut(
        id=str(row["id"]),
        user_id=str(row["user_id"]),
        name=user["name"] if user else "",
        body=row["body"],
        created_at=row["created_at"],
    )


def _signed(live: list[dict], user_id: str) -> bool:
    return any(str(r["user_id"]) == user_id and r["decision"] == "approved" for r in live)


def _summary_fields(conn: Any, row: dict, revisions: list[dict]) -> dict:
    change_id = str(row["id"])
    creator = users.by_id(conn, str(row["created_by"]))
    titles = []
    for rev in revisions:
        doc = documents.document(conn, str(rev["document_id"]))
        if doc:
            titles.append(doc["title"])
    waiting: list[str] = []
    if row["status"] == "approval":
        live = changes.live_approvals(conn, change_id)
        waiting = [
            a["name"]
            for a in changes.approvers(conn, change_id)
            if not _signed(live, str(a["user_id"]))
        ]
    return {
        "id": change_id,
        "number": display_number(row["number"]),
        "title": row["title"],
        "status": str(row["status"]),
        "created_by": str(row["created_by"]),
        "created_by_name": creator["name"] if creator else "",
        "created_at": row["created_at"],
        "documents": titles,
        "waiting_on": waiting,
    }


def change_summary(conn: Any, row: dict) -> ChangeSummary:
    revisions = documents.revisions_for_change(conn, str(row["id"]))
    return ChangeSummary(**_summary_fields(conn, row, revisions))


def change_detail(conn: Any, row: dict) -> ChangeDetail:
    change_id = str(row["id"])
    revisions = documents.revisions_for_change(conn, change_id)
    live = changes.live_approvals(conn, change_id)

    def state(user_id: str) -> str:
        if _signed(live, user_id):
            return "signed"
        if any(str(r["user_id"]) == user_id and r["decision"] == "changes_requested" for r in live):
            return "changes_requested"
        return "pending"

    approvers = [
        ApproverOut(
            user_id=str(a["user_id"]),
            name=a["name"],
            email=a["email"],
            role=str(a["role"]),
            state=state(str(a["user_id"])),  # type: ignore[arg-type]
        )
        for a in changes.approvers(conn, change_id)
    ]
    approvals = [
        ApprovalOut(
            id=str(r["id"]),
            user_id=str(r["user_id"]),
            name=r["name"],
            email=r["email"],
            decision=str(r["decision"]),
            comment=r["comment"],
            signed_at=r["signed_at"],
            voided_at=r["voided_at"],
            voided_reason=r["voided_reason"],
        )
        for r in changes.all_approvals(conn, change_id)
    ]
    comments = [
        CommentOut(
            id=str(r["id"]),
            user_id=str(r["user_id"]),
            name=r["name"],
            body=r["body"],
            created_at=r["created_at"],
        )
        for r in changes.comments_with_names(conn, change_id)
    ]
    event_rows = event_outs(conn, events.for_change(conn, change_id))
    return ChangeDetail(
        **_summary_fields(conn, row, revisions),
        description=row["description"],
        reason=row["reason"],
        justification=row["justification"],
        cutin_date=row["cutin_date"],
        submitted_at=row["submitted_at"],
        approved_at=row["approved_at"],
        closed_at=row["closed_at"],
        revisions=[revision_out(conn, r) for r in revisions],
        approvers=approvers,
        approvals=approvals,
        comments=comments,
        events=event_rows,
    )


def event_outs(conn: Any, rows: list[dict]) -> list[EventOut]:
    names = {str(u["id"]): u["name"] for u in users.list_all(conn)}
    return [
        EventOut(
            id=str(e["id"]),
            at=e["at"],
            actor_user_id=str(e["actor_user_id"]) if e["actor_user_id"] else None,
            actor_name=names.get(str(e["actor_user_id"])) if e["actor_user_id"] else None,
            entity_type=e["entity_type"],
            entity_id=str(e["entity_id"]),
            action=e["action"],
            detail=e["detail"] or {},
        )
        for e in rows
    ]


def document_summary(row: dict) -> DocumentSummary:
    return DocumentSummary(
        id=str(row["document_id"]),
        title=row["title"],
        current_revision_id=str(row["current_revision_id"]),
        revision_number=row["revision_number"],
        released_at=row["released_at"],
        released_by_name=row["released_by_name"],
        original_filename=row["original_filename"],
        rank=float(row["rank"]),
    )


def document_detail_out(detail: dict) -> DocumentDetail:
    revisions = [
        DocumentRevisionOut(
            id=str(r["id"]),
            document_id=str(r["document_id"]),
            document_title=detail["title"],
            revision_number=r["revision_number"],
            original_filename=r["original_filename"],
            content_type=r["content_type"],
            byte_size=r["byte_size"],
            sha256=r["sha256"],
            has_redline=r["redline_gcs_key"] is not None,
            uploaded_by=str(r["uploaded_by"]),
            uploaded_at=r["uploaded_at"],
            released_at=r["released_at"],
            change_id=str(r["change_id"]),
            change_number=r["change_display"],
            change_title=r["change_title"],
            change_status=str(r["change_status"]),
            cutin_date=r["cutin_date"],
            approvals=[
                {**a, "signed_at": a["signed_at"].isoformat() if a["signed_at"] else None}
                for a in r["approvals"]
            ],
        )
        for r in detail["revisions"]
    ]
    return DocumentDetail(
        id=str(detail["id"]),
        title=detail["title"],
        created_at=detail["created_at"],
        current_revision_id=(
            str(detail["current_revision_id"]) if detail["current_revision_id"] else None
        ),
        revisions=revisions,
    )
