from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, field_validator

from api.auth import current_user, require_doc_manager
from api.deps import get_conn_dep
from api.schemas import UserOut, user_out
from repo import users
from services import users as user_service

router = APIRouter()

Role = Literal["engineering", "operations", "quality", "other"]


class InviteBody(BaseModel):
    email: str
    name: str
    role: Role
    is_doc_manager: bool = False

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        v = v.strip()
        if "@" not in v:
            raise ValueError("email must contain @")
        return v

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name must not be empty")
        return v


class UpdateBody(BaseModel):
    role: Role | None = None
    is_doc_manager: bool | None = None
    deactivated: bool | None = None


@router.get("/users")
def list_users(_user: dict = Depends(current_user), conn=Depends(get_conn_dep)) -> list[UserOut]:
    rows = sorted(users.list_all(conn), key=lambda r: (r["name"].lower(), r["email"]))
    return [user_out(r) for r in rows]


@router.post("/users", status_code=201)
def invite_user(
    body: InviteBody, actor: dict = Depends(require_doc_manager), conn=Depends(get_conn_dep)
) -> UserOut:
    return user_out(
        user_service.invite(
            conn,
            actor,
            email=body.email,
            name=body.name,
            role=body.role,
            is_doc_manager=body.is_doc_manager,
        )
    )


@router.patch("/users/{user_id}")
def update_user(
    user_id: str,
    body: UpdateBody,
    actor: dict = Depends(require_doc_manager),
    conn=Depends(get_conn_dep),
) -> UserOut:
    return user_out(
        user_service.update(conn, actor, user_id, **body.model_dump(exclude_unset=True))
    )
