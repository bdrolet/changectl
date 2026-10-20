from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=False)


class UserOut(_Out):
    id: str
    email: str
    name: str
    role: str
    is_doc_manager: bool
    deactivated: bool


def user_out(row: dict) -> UserOut:
    return UserOut(
        id=str(row["id"]),
        email=row["email"],
        name=row["name"],
        role=str(row["role"]),
        is_doc_manager=row["is_doc_manager"],
        deactivated=row["deactivated_at"] is not None,
    )


class ChangeSummary(_Out):
    id: str
    number: str
    title: str
    status: str
    created_by: str
    created_by_name: str
    created_at: datetime
    documents: list[str]
    waiting_on: list[str]


class RevisionOut(_Out):
    id: str
    document_id: str
    document_title: str
    revision_number: int | None
    original_filename: str
    content_type: str
    byte_size: int
    sha256: str
    has_redline: bool
    uploaded_by: str
    uploaded_at: datetime
    released_at: datetime | None
    superseded_at: datetime | None
    next_revision_number: int | None


class ApproverOut(_Out):
    user_id: str
    name: str
    email: str
    role: str
    state: Literal["signed", "pending", "changes_requested"]


class ApprovalOut(_Out):
    id: str
    user_id: str
    name: str
    email: str
    decision: str
    comment: str | None
    signed_at: datetime
    voided_at: datetime | None
    voided_reason: str | None


class CommentOut(_Out):
    id: str
    user_id: str
    name: str
    body: str
    created_at: datetime


class EventOut(_Out):
    id: str
    at: datetime
    actor_user_id: str | None
    actor_name: str | None
    entity_type: str
    entity_id: str
    action: str
    detail: dict


class ChangeDetail(ChangeSummary):
    description: str
    reason: str
    justification: str
    cutin_date: date | None
    submitted_at: datetime | None
    approved_at: datetime | None
    closed_at: datetime | None
    revisions: list[RevisionOut]
    approvers: list[ApproverOut]
    approvals: list[ApprovalOut]
    comments: list[CommentOut]
    events: list[EventOut]


class DocumentSummary(_Out):
    id: str
    title: str
    current_revision_id: str | None
    revision_number: int | None
    released_at: datetime | None
    released_by_name: str | None
    original_filename: str | None
    rank: float


class DocumentRevisionOut(RevisionOut):
    change_id: str
    change_number: str
    change_title: str
    change_status: str
    cutin_date: date | None
    approvals: list[dict]


class DocumentDetail(_Out):
    id: str
    title: str
    created_at: datetime
    current_revision_id: str | None
    revisions: list[DocumentRevisionOut]
