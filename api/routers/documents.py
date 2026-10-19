from typing import Literal

from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from starlette.concurrency import run_in_threadpool

from api import assemble
from api.auth import current_user
from api.deps import get_conn_dep, get_storage
from api.ids import uid
from api.schemas import DocumentDetail, DocumentSummary
from clients.storage import Storage, safe_filename
from models.errors import LifecycleError
from repo import documents as documents_repo
from repo import events
from services import search

router = APIRouter()


@router.get("/documents")
def search_documents(
    q: str = "", _user: dict = Depends(current_user), conn=Depends(get_conn_dep)
) -> list[DocumentSummary]:
    return [assemble.document_summary(r) for r in search.search_documents(conn, q)]


@router.get("/documents/{document_id}")
def get_document(
    document_id: str, _user: dict = Depends(current_user), conn=Depends(get_conn_dep)
) -> DocumentDetail:
    detail = search.document_detail(conn, uid(document_id))
    if detail is None:
        raise LifecycleError("not_found", "document not found")
    return assemble.document_detail_out(detail)


@router.get("/revisions/{revision_id}/download")
async def download_revision(
    revision_id: str,
    which: Literal["released", "redline"] = "released",
    actor: dict = Depends(current_user),
    conn=Depends(get_conn_dep),
    storage: Storage = Depends(get_storage),
) -> RedirectResponse:
    rid = uid(revision_id)
    rev = documents_repo.revision(conn, rid)
    if rev is None:
        raise LifecycleError("not_found", "revision not found")
    if which == "redline":
        if rev["redline_gcs_key"] is None:
            raise LifecycleError("not_found", "no redline for this revision")
        key = rev["redline_gcs_key"]
        filename = "redline-" + safe_filename(rev["original_filename"])
    else:
        key = rev["gcs_key"]
        filename = safe_filename(rev["original_filename"])
    events.record(
        conn,
        actor_user_id=actor["id"],
        entity_type="revision",
        entity_id=rid,
        action="revision.downloaded",
        detail={"change_id": str(rev["change_id"]), "which": which},
    )
    url = await run_in_threadpool(storage.signed_url, key, filename)
    return RedirectResponse(url, status_code=302)
