from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, Request, Response, UploadFile
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

import clients.otel as otel
from api import assemble
from api.auth import current_user
from api.deps import get_conn_dep, get_storage
from api.ids import uid
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
    cutin_date: date | None = None


class CommentBody(BaseModel):
    body: str


def _detail(conn, change_id: str) -> ChangeDetail:
    return assemble.change_detail(conn, changes_repo.get(conn, change_id))  # type: ignore[arg-type]


_UPLOAD_NOTE = (
    f"PDF, DOCX or XLSX only, sniffed from content; maximum {lifecycle.MAX_UPLOAD_BYTES} "
    f"bytes (25 MB)."
)


@router.post("", status_code=201)
def create_change(
    body: CreateBody,
    actor: dict = Depends(current_user),
    conn=Depends(get_conn_dep, scope="function"),
) -> ChangeDetail:
    row = lifecycle.create_change(conn, actor, **body.model_dump())
    return assemble.change_detail(conn, row)


@router.get("")
def list_changes(
    status: Status | None = None,
    _user: dict = Depends(current_user),
    conn=Depends(get_conn_dep, scope="function"),
) -> list[ChangeSummary]:
    return [assemble.change_summary(conn, r) for r in changes_repo.list_by_status(conn, status)]


@router.get("/{change_id}")
def get_change(
    change_id: str,
    _user: dict = Depends(current_user),
    conn=Depends(get_conn_dep, scope="function"),
) -> ChangeDetail:
    cid = uid(change_id)
    row = changes_repo.get(conn, cid)
    if row is None:
        raise LifecycleError("not_found", "change not found")
    return assemble.change_detail(conn, row)


@router.patch("/{change_id}")
def patch_change(
    change_id: str,
    body: PatchBody,
    actor: dict = Depends(current_user),
    conn=Depends(get_conn_dep, scope="function"),
) -> ChangeDetail:
    row = lifecycle.update_change(conn, actor, uid(change_id), **body.model_dump())
    return assemble.change_detail(conn, row)


@router.post("/{change_id}/revisions", status_code=201, description=_UPLOAD_NOTE)
async def attach_revision(
    change_id: str,
    file: UploadFile = File(...),
    document_id: str | None = Form(None),
    title: str | None = Form(None),
    actor: dict = Depends(current_user),
    conn=Depends(get_conn_dep, scope="function"),
    storage: Storage = Depends(get_storage),
) -> RevisionOut:
    cid = uid(change_id)
    did = uid(document_id) if document_id else None
    data = await file.read()
    rev = await run_in_threadpool(
        lifecycle.attach_revision,
        conn,
        actor,
        cid,
        filename=file.filename or "upload",
        data=data,
        storage=storage,
        document_id=did,
        title=title,
    )
    otel.uploads.add(1, {"kind": "revision"})
    return await run_in_threadpool(assemble.revision_out, conn, rev)


@router.delete("/{change_id}/revisions/{revision_id}", status_code=204)
def remove_revision(
    change_id: str,
    revision_id: str,
    actor: dict = Depends(current_user),
    conn=Depends(get_conn_dep, scope="function"),
) -> Response:
    lifecycle.remove_revision(conn, actor, uid(change_id), uid(revision_id))
    return Response(status_code=204)


@router.put("/{change_id}/approvers")
def put_approvers(
    change_id: str,
    body: ApproversBody,
    actor: dict = Depends(current_user),
    conn=Depends(get_conn_dep, scope="function"),
) -> ChangeDetail:
    cid = uid(change_id)
    lifecycle.set_approvers(conn, actor, cid, [uid(u) for u in body.user_ids])
    return _detail(conn, cid)


@router.post("/{change_id}/submit")
def submit_change(
    change_id: str,
    actor: dict = Depends(current_user),
    conn=Depends(get_conn_dep, scope="function"),
) -> ChangeDetail:
    return assemble.change_detail(conn, lifecycle.submit(conn, actor, uid(change_id)))


@router.post("/{change_id}/approve")
def approve_change(
    change_id: str,
    request: Request,
    body: ApproveBody | None = None,
    actor: dict = Depends(current_user),
    conn=Depends(get_conn_dep, scope="function"),
) -> ChangeDetail:
    cid = uid(change_id)
    comment = body.comment if body else None
    lifecycle.approve(conn, actor, cid, google_sub=request.state.google_sub, comment=comment)
    return _detail(conn, cid)


@router.post("/{change_id}/request-changes")
def request_changes(
    change_id: str,
    request: Request,
    body: RequestChangesBody,
    actor: dict = Depends(current_user),
    conn=Depends(get_conn_dep, scope="function"),
) -> ChangeDetail:
    cid = uid(change_id)
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
    conn=Depends(get_conn_dep, scope="function"),
    storage: Storage = Depends(get_storage),
) -> RevisionOut:
    cid = uid(change_id)
    rid = uid(revision_id)
    data = await file.read()
    rev = await run_in_threadpool(
        lifecycle.replace_release_file,
        conn,
        actor,
        cid,
        rid,
        filename=file.filename or "upload",
        data=data,
        storage=storage,
    )
    otel.uploads.add(1, {"kind": "release_file"})
    return await run_in_threadpool(assemble.revision_out, conn, rev)


@router.post("/{change_id}/release")
def release_change(
    change_id: str,
    body: ReleaseBody,
    actor: dict = Depends(current_user),
    conn=Depends(get_conn_dep, scope="function"),
) -> ChangeDetail:
    row = lifecycle.release(conn, actor, uid(change_id), cutin_date=body.cutin_date)
    return assemble.change_detail(conn, row)


@router.post("/{change_id}/comments", status_code=201)
def add_comment(
    change_id: str,
    body: CommentBody,
    actor: dict = Depends(current_user),
    conn=Depends(get_conn_dep, scope="function"),
) -> CommentOut:
    row = lifecycle.add_comment(conn, actor, uid(change_id), body.body)
    return assemble.comment_out(conn, row)
