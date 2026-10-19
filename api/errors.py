from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from models.errors import LifecycleError

STATUS_BY_CODE: dict[str, int] = {
    "not_found": 404,
    "forbidden": 403,
    "self_approval": 403,
    "not_an_approver": 403,
    "wrong_status": 409,
    "locked": 409,
    "document_busy": 409,
    "type_mismatch": 409,
    "too_large": 413,
    "invalid_file": 415,
    "no_approvers": 422,
    "no_revisions": 422,
    "cutin_required": 422,
    "comment_required": 422,
}


def install(app: FastAPI) -> None:
    @app.exception_handler(LifecycleError)
    async def lifecycle_error(_request: Request, exc: LifecycleError) -> JSONResponse:
        return JSONResponse(
            status_code=STATUS_BY_CODE.get(exc.code, 500),
            content={"detail": exc.code, "message": exc.detail},
        )
