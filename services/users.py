from typing import Any
from uuid import UUID

from models.display import display_number
from models.errors import LifecycleError
from repo import changes, events, users


def _active_doc_managers(conn: Any) -> int:
    row = conn.execute(
        "SELECT count(*) AS n FROM users WHERE is_doc_manager AND deactivated_at IS NULL"
    ).fetchone()
    return int(row["n"])


def invite(
    conn: Any, actor: dict, *, email: str, name: str, role: str, is_doc_manager: bool
) -> dict:
    email = email.strip().lower()
    if users.by_email(conn, email) is not None:
        raise LifecycleError("duplicate_email", email)
    user = users.insert(
        conn,
        email=email,
        name=name,
        role=role,
        is_doc_manager=is_doc_manager,
        invited_by=str(actor["id"]),
    )
    events.record(
        conn,
        actor_user_id=str(actor["id"]),
        entity_type="user",
        entity_id=str(user["id"]),
        action="user.invited",
        detail={"email": email, "role": role, "is_doc_manager": is_doc_manager},
    )
    return user


def update(
    conn: Any,
    actor: dict,
    user_id: str,
    *,
    role: str | None = None,
    is_doc_manager: bool | None = None,
    deactivated: bool | None = None,
) -> dict:
    try:
        UUID(user_id)
    except ValueError:
        raise LifecycleError("not_found", "user") from None
    target = users.by_id(conn, user_id)
    if target is None:
        raise LifecycleError("not_found", "user")

    if deactivated is True:
        awaiting = changes.open_changes_awaiting(conn, user_id)
        if awaiting:
            numbers = [display_number(c["number"]) for c in awaiting]
            raise LifecycleError(
                "pending_approver",
                f"pending approver on {', '.join(numbers)}",
                extra={"changes": numbers},
            )

    is_self = str(target["id"]) == str(actor["id"])
    loses_manager = is_doc_manager is False or deactivated is True
    if is_self and loses_manager and target["is_doc_manager"]:
        if _active_doc_managers(conn) <= 1:
            raise LifecycleError("last_doc_manager", "at least one doc manager must remain")

    updated = users.update(
        conn, user_id, role=role, is_doc_manager=is_doc_manager, deactivated=deactivated
    )
    changed = {
        k: v
        for k, v in {
            "role": role,
            "is_doc_manager": is_doc_manager,
            "deactivated": deactivated,
        }.items()
        if v is not None
    }
    events.record(
        conn,
        actor_user_id=str(actor["id"]),
        entity_type="user",
        entity_id=user_id,
        action="user.updated",
        detail=changed,
    )
    return updated
