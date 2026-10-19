import uuid
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, Request, Response, UploadFile
from pydantic import BaseModel

import clients.otel as otel
from api import assemble
from api.auth import current_user
from api.deps import get_conn_dep, get_storage
from api.schemas import ChangeDetail, ChangeSummary, CommentOut, RevisionOut
from clients.storage import Storage
from models.errors import LifecycleError
from repo import changes as changes_repo
from services import lifecycle

router = APIRouter(prefix="/changes")

Status = Literal["initiate", "approval", "implementation", "closed"]


class CreateBody(BaseModel):
    title: str
    description: str
    reason: str
    justification: str


class PatchBody(BaseModel):
    title: str | None = None
    description: str | None = None
    reason: str | None = None
    justification: str | None = None


class ApproversBody(BaseModel):
    user_ids: list[str]


class ApproveBody(BaseModel):
    comment: str | None = None


class RequestChangesBody(BaseModel):
    comment: str


class ReleaseBody(BaseModel):
    cutin_date: date


class CommentBody(BaseModel):
    body: str


def _uid(value: str) -> str:
    try:
        return str(uuid.UUID(value))
    except ValueError:
        raise LifecycleError("not_found", "not found") from None


def _detail(conn, change_id: str) -> ChangeDetail:
    return assemble.change_detail(conn, changes_repo.get(conn, change_id))  # type: ignore[arg-type]


_UPLOAD_NOTE = (
    f"PDF, DOCX or XLSX only, sniffed from content; maximum {lifecycle.MAX_UPLOAD_BYTES} "
    f"bytes (25 MB)."
)


@router.post("", status_code=201)
def create_change(
    body: CreateBody, actor: dict = Depends(current_user), conn=Depends(get_conn_dep)
) -> ChangeDetail:
    row = lifecycle.create_change(conn, actor, **body.model_dump())
    return assemble.change_detail(conn, row)


@router.get("")
def list_changes(
    status: Status | None = None,
    _user: dict = Depends(current_user),
    conn=Depends(get_conn_dep),
) -> list[ChangeSummary]:
    return [assemble.change_summary(conn, r) for r in changes_repo.list_by_status(conn, status)]


@router.get("/{change_id}")
def get_change(
    change_id: str, _user: dict = Depends(current_user), conn=Depends(get_conn_dep)
) -> ChangeDetail:
    cid = _uid(change_id)
    row = changes_repo.get(conn, cid)
    if row is None:
        raise LifecycleError("not_found", "change not found")
    return assemble.change_detail(conn, row)


@router.patch("/{change_id}")
def patch_change(
    change_id: str,
    body: PatchBody,
    actor: dict = Depends(current_user),
    conn=Depends(get_conn_dep),
) -> ChangeDetail:
    row = lifecycle.update_change(conn, actor, _uid(change_id), **body.model_dump())
    return assemble.change_detail(conn, row)


@router.post("/{change_id}/revisions", status_code=201, description=_UPLOAD_NOTE)
async def attach_revision(
    change_id: str,
    file: UploadFile = File(...),
    document_id: str | None = Form(None),
    title: str | None = Form(None),
    actor: dict = Depends(current_user),
    conn=Depends(get_conn_dep),
    storage: Storage = Depends(get_storage),
) -> RevisionOut:
    data = await file.read()
    rev = lifecycle.attach_revision(
        conn,
        actor,
        _uid(change_id),
        filename=file.filename or "upload",
        data=data,
        storage=storage,
        document_id=_uid(document_id) if document_id else None,
        title=title,
    )
    otel.uploads.add(1, {"kind": "revision"})
    return assemble.revision_out(conn, rev)


@router.delete("/{change_id}/revisions/{revision_id}", status_code=204)
def remove_revision(
    change_id: str,
    revision_id: str,
    actor: dict = Depends(current_user),
    conn=Depends(get_conn_dep),
) -> Response:
    lifecycle.remove_revision(conn, actor, _uid(change_id), _uid(revision_id))
    return Response(status_code=204)


@router.put("/{change_id}/approvers")
def put_approvers(
    change_id: str,
    body: ApproversBody,
    actor: dict = Depends(current_user),
    conn=Depends(get_conn_dep),
) -> ChangeDetail:
    cid = _uid(change_id)
    lifecycle.set_approvers(conn, actor, cid, [_uid(u) for u in body.user_ids])
    return _detail(conn, cid)


@router.post("/{change_id}/submit")
def submit_change(
    change_id: str, actor: dict = Depends(current_user), conn=Depends(get_conn_dep)
) -> ChangeDetail:
    return assemble.change_detail(conn, lifecycle.submit(conn, actor, _uid(change_id)))


@router.post("/{change_id}/approve")
def approve_change(
    change_id: str,
    request: Request,
    body: ApproveBody,
    actor: dict = Depends(current_user),
    conn=Depends(get_conn_dep),
) -> ChangeDetail:
    cid = _uid(change_id)
    lifecycle.approve(conn, actor, cid, google_sub=request.state.google_sub, comment=body.comment)
    return _detail(conn, cid)


@router.post("/{change_id}/request-changes")
def request_changes(
    change_id: str,
    request: Request,
    body: RequestChangesBody,
    actor: dict = Depends(current_user),
    conn=Depends(get_conn_dep),
) -> ChangeDetail:
    cid = _uid(change_id)
    lifecycle.request_changes(
        conn, actor, cid, google_sub=request.state.google_sub, comment=body.comment
    )
    return _detail(conn, cid)


@router.post("/{change_id}/revisions/{revision_id}/release-file", description=_UPLOAD_NOTE)
async def release_file(
    change_id: str,
    revision_id: str,
    file: UploadFile = File(...),
    actor: dict = Depends(current_user),
    conn=Depends(get_conn_dep),
    storage: Storage = Depends(get_storage),
) -> RevisionOut:
    data = await file.read()
    rev = lifecycle.replace_release_file(
        conn,
        actor,
        _uid(change_id),
        _uid(revision_id),
        filename=file.filename or "upload",
        data=data,
        storage=storage,
    )
    otel.uploads.add(1, {"kind": "release_file"})
    return assemble.revision_out(conn, rev)


@router.post("/{change_id}/release")
def release_change(
    change_id: str,
    body: ReleaseBody,
    actor: dict = Depends(current_user),
    conn=Depends(get_conn_dep),
) -> ChangeDetail:
    row = lifecycle.release(conn, actor, _uid(change_id), cutin_date=body.cutin_date)
    return assemble.change_detail(conn, row)


@router.post("/{change_id}/comments", status_code=201)
def add_comment(
    change_id: str,
    body: CommentBody,
    actor: dict = Depends(current_user),
    conn=Depends(get_conn_dep),
) -> CommentOut:
    row = lifecycle.add_comment(conn, actor, _uid(change_id), body.body)
    return assemble.comment_out(conn, row)
