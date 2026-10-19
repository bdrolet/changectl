"""Change lifecycle: initiate -> approval -> implementation -> closed.

The caller owns the transaction; nothing here commits or rolls back.
"""

import hashlib
from datetime import date, datetime, timezone
from typing import Any

from clients.storage import Storage, object_key
from models.errors import LifecycleError
from repo import changes, documents, events, users
from services.extract import ACCEPTED, extract_text, sniff_type

MAX_UPLOAD_BYTES = 26_214_400


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load_change(conn: Any, change_id: str) -> dict:
    change = changes.get(conn, change_id)
    if change is None:
        raise LifecycleError("not_found", "change not found")
    return change


def _require_status(change: dict, status: str) -> None:
    if change["status"] != status:
        raise LifecycleError(
            "wrong_status", f"change is in '{change['status']}', expected '{status}'"
        )


def _require_editable(change: dict) -> None:
    if change["status"] != "initiate":
        raise LifecycleError("locked", "the record is locked once the change is submitted")


def _require_creator(actor: dict, change: dict) -> None:
    if str(change["created_by"]) != str(actor["id"]):
        raise LifecycleError("forbidden", "only the change creator may do this")


def _require_doc_manager(actor: dict) -> None:
    if not actor["is_doc_manager"]:
        raise LifecycleError("forbidden", "document manager role required")


def _check_upload(data: bytes) -> str:
    if len(data) > MAX_UPLOAD_BYTES:
        raise LifecycleError("too_large", f"file exceeds {MAX_UPLOAD_BYTES} bytes")
    content_type = sniff_type(data)
    if content_type is None or content_type not in ACCEPTED:
        raise LifecycleError("invalid_file", "only PDF, DOCX and XLSX files are accepted")
    return content_type


def _record(
    conn: Any,
    actor: dict,
    entity_type: str,
    entity_id: Any,
    action: str,
    detail: dict | None = None,
) -> None:
    events.record(
        conn,
        actor_user_id=str(actor["id"]),
        entity_type=entity_type,
        entity_id=str(entity_id),
        action=action,
        detail=detail,
    )


def _store_upload(
    conn: Any,
    storage: Storage,
    *,
    document_id: str,
    change_id: str,
    actor: dict,
    filename: str,
    data: bytes,
    content_type: str,
) -> dict:
    """Insert the revision row, then store its bytes under its own key."""
    sha = _sha256(data)
    # The key embeds the revision id, so insert with a placeholder and fix it up.
    rev = documents.insert_revision(
        conn,
        document_id=document_id,
        change_id=change_id,
        original_filename=filename,
        content_type=content_type,
        byte_size=len(data),
        sha256=sha,
        gcs_key="pending",
        extracted_text=extract_text(content_type, data),
        uploaded_by=str(actor["id"]),
    )
    key = object_key(document_id, str(rev["id"]), filename)
    storage.put(key, data, content_type)
    documents.set_gcs_key(conn, str(rev["id"]), key)
    rev["gcs_key"] = key
    return rev


def create_change(
    conn: Any, actor: dict, *, title: str, description: str, reason: str, justification: str
) -> dict:
    change = changes.insert(
        conn,
        title=title,
        description=description,
        reason=reason,
        justification=justification,
        created_by=str(actor["id"]),
    )
    _record(conn, actor, "change", change["id"], "change.created", {"title": title})
    return change


def update_change(conn: Any, actor: dict, change_id: str, **fields: Any) -> dict:
    change = _load_change(conn, change_id)
    _require_editable(change)
    _require_creator(actor, change)
    allowed = {"title", "description", "reason", "justification"}
    values = {k: v for k, v in fields.items() if k in allowed and v is not None}
    updated = changes.update_fields(conn, change_id, **values)
    _record(conn, actor, "change", change_id, "change.updated", {"fields": sorted(values)})
    return updated


def attach_revision(
    conn: Any,
    actor: dict,
    change_id: str,
    *,
    filename: str,
    data: bytes,
    storage: Storage,
    document_id: str | None = None,
    title: str | None = None,
) -> dict:
    change = _load_change(conn, change_id)
    _require_editable(change)
    _require_creator(actor, change)
    content_type = _check_upload(data)
    if document_id is not None:
        if documents.document(conn, document_id) is None:
            raise LifecycleError("not_found", "document not found")
        if documents.pending_revision_exists(conn, document_id):
            raise LifecycleError("document_busy", "document already has a pending revision")
    elif not title:
        raise LifecycleError("invalid_file", "a title or an existing document is required")
    else:
        document_id = str(
            documents.insert_document(conn, title=title, created_by=str(actor["id"]))["id"]
        )
    rev = _store_upload(
        conn,
        storage,
        document_id=document_id,
        change_id=change_id,
        actor=actor,
        filename=filename,
        data=data,
        content_type=content_type,
    )
    changes.link_revision(conn, change_id, str(rev["id"]))
    _record(
        conn,
        actor,
        "revision",
        rev["id"],
        "revision.attached",
        {"change_id": change_id, "document_id": document_id, "sha256": rev["sha256"]},
    )
    return rev


def remove_revision(conn: Any, actor: dict, change_id: str, revision_id: str) -> None:
    change = _load_change(conn, change_id)
    _require_editable(change)
    _require_creator(actor, change)
    rev = documents.revision(conn, revision_id)
    if rev is None or str(rev["change_id"]) != str(change_id):
        raise LifecycleError("not_found", "revision not found on this change")
    document_id = str(rev["document_id"])
    documents.delete_revision(conn, revision_id)
    if not documents.revisions_for_document(conn, document_id):
        documents.delete_document(conn, document_id)
    _record(
        conn,
        actor,
        "revision",
        revision_id,
        "revision.removed",
        {"change_id": change_id, "document_id": document_id},
    )


def set_approvers(conn: Any, actor: dict, change_id: str, user_ids: list[str]) -> list[dict]:
    change = _load_change(conn, change_id)
    _require_editable(change)
    _require_creator(actor, change)
    ids = [str(u) for u in user_ids]
    if str(change["created_by"]) in ids:
        raise LifecycleError("self_approval", "you cannot approve your own change")
    for uid in ids:
        user = users.by_id(conn, uid)
        if user is None or user["deactivated_at"] is not None:
            raise LifecycleError("not_found", f"no active user {uid}")
    changes.set_approvers(conn, change_id, ids, str(actor["id"]))
    result = changes.approvers(conn, change_id)
    _record(conn, actor, "change", change_id, "change.approvers_set", {"user_ids": ids})
    return result


def submit(conn: Any, actor: dict, change_id: str) -> dict:
    change = _load_change(conn, change_id)
    _require_status(change, "initiate")
    _require_creator(actor, change)
    if not changes.approvers(conn, change_id):
        raise LifecycleError("no_approvers", "add at least one approver")
    if not documents.revisions_for_change(conn, change_id):
        raise LifecycleError("no_revisions", "attach at least one file")
    changes.void_approvals(conn, change_id, "resubmitted", _now())
    updated = changes.set_status(conn, change_id, "approval", at=_now())
    _record(conn, actor, "change", change_id, "change.submitted")
    return updated


def approve(
    conn: Any, actor: dict, change_id: str, *, google_sub: str, comment: str | None
) -> dict:
    changes.lock(conn, change_id)
    change = _load_change(conn, change_id)
    _require_status(change, "approval")
    approver_ids = {str(a["user_id"]) for a in changes.approvers(conn, change_id)}
    if str(actor["id"]) not in approver_ids:
        raise LifecycleError("not_an_approver", "you are not an approver on this change")
    if str(change["created_by"]) == str(actor["id"]):
        raise LifecycleError("self_approval", "you cannot approve your own change")
    live = changes.live_approvals(conn, change_id)
    for row in live:
        if str(row["user_id"]) == str(actor["id"]) and row["decision"] == "approved":
            return row
    hashes = sorted(r["sha256"] for r in documents.revisions_for_change(conn, change_id))
    approval = changes.insert_approval(
        conn,
        change_id=change_id,
        user_id=str(actor["id"]),
        google_sub=google_sub,
        email=actor["email"],
        decision="approved",
        comment=comment,
        file_sha256s=hashes,
    )
    _record(
        conn, actor, "change", change_id, "change.approved", {"approval_id": str(approval["id"])}
    )
    approved = {
        str(r["user_id"])
        for r in changes.live_approvals(conn, change_id)
        if r["decision"] == "approved"
    }
    if approver_ids <= approved:
        changes.set_status(conn, change_id, "implementation", at=_now())
        _record(conn, actor, "change", change_id, "change.approval_complete")
    return approval


def request_changes(
    conn: Any, actor: dict, change_id: str, *, google_sub: str, comment: str
) -> dict:
    changes.lock(conn, change_id)
    change = _load_change(conn, change_id)
    _require_status(change, "approval")
    approver_ids = {str(a["user_id"]) for a in changes.approvers(conn, change_id)}
    if str(actor["id"]) not in approver_ids:
        raise LifecycleError("not_an_approver", "you are not an approver on this change")
    if not comment or not comment.strip():
        raise LifecycleError("comment_required", "a comment is required when requesting changes")
    changes.void_approvals(conn, change_id, f"changes_requested_by:{actor['email']}", _now())
    row = changes.insert_approval(
        conn,
        change_id=change_id,
        user_id=str(actor["id"]),
        google_sub=google_sub,
        email=actor["email"],
        decision="changes_requested",
        comment=comment,
        file_sha256s=[],
    )
    changes.set_status(conn, change_id, "initiate", at=_now())
    _record(conn, actor, "change", change_id, "change.changes_requested", {"comment": comment})
    return row


def replace_release_file(
    conn: Any,
    actor: dict,
    change_id: str,
    revision_id: str,
    *,
    filename: str,
    data: bytes,
    storage: Storage,
) -> dict:
    change = _load_change(conn, change_id)
    _require_status(change, "implementation")
    _require_doc_manager(actor)
    rev = documents.revision(conn, revision_id)
    if rev is None or str(rev["change_id"]) != str(change_id):
        raise LifecycleError("not_found", "revision not found on this change")
    content_type = _check_upload(data)
    if content_type != rev["content_type"]:
        raise LifecycleError("type_mismatch", "replacement must be the same file type")
    sha = _sha256(data)
    first = rev["redline_sha256"] is None
    key = object_key(str(rev["document_id"]), revision_id, f"released-{sha[:8]}-{filename}")
    storage.put(key, data, content_type)
    updated = documents.set_release_file(
        conn,
        revision_id,
        gcs_key=key,
        sha256=sha,
        content_type=content_type,
        byte_size=len(data),
        original_filename=filename,
        extracted_text=extract_text(content_type, data),
        redline_gcs_key=rev["gcs_key"] if first else rev["redline_gcs_key"],
        redline_sha256=rev["sha256"] if first else rev["redline_sha256"],
    )
    _record(
        conn,
        actor,
        "revision",
        revision_id,
        "revision.release_file_replaced",
        {"change_id": change_id, "old_sha256": rev["sha256"], "new_sha256": sha},
    )
    return updated


def release(conn: Any, actor: dict, change_id: str, *, cutin_date: date | None) -> dict:
    change = _load_change(conn, change_id)
    _require_status(change, "implementation")
    _require_doc_manager(actor)
    if cutin_date is None:
        raise LifecycleError("cutin_required", "cutin_date is required")
    at = _now()
    released: list[dict] = []
    for rev in documents.revisions_for_change(conn, change_id):
        document_id = str(rev["document_id"])
        documents.lock(conn, document_id)
        number = documents.next_revision_number(conn, document_id)
        done = documents.release(
            conn,
            str(rev["id"]),
            revision_number=number,
            released_by=str(actor["id"]),
            released_at=at,
        )
        documents.supersede_current(conn, document_id, str(rev["id"]), at)
        released.append(
            {
                "revision_id": str(done["id"]),
                "document_id": document_id,
                "revision_number": number,
                "sha256": done["sha256"],
                "redline_sha256": done["redline_sha256"],
            }
        )
    changes.set_cutin(conn, change_id, cutin_date)
    closed = changes.set_status(conn, change_id, "closed", at=at)
    _record(
        conn,
        actor,
        "change",
        change_id,
        "change.released",
        {"revisions": released, "cutin_date": cutin_date.isoformat()},
    )
    return closed


def add_comment(conn: Any, actor: dict, change_id: str, body: str) -> dict:
    _load_change(conn, change_id)
    comment = changes.insert_comment(conn, change_id=change_id, user_id=str(actor["id"]), body=body)
    _record(
        conn, actor, "change", change_id, "change.commented", {"comment_id": str(comment["id"])}
    )
    return comment
