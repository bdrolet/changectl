from typing import Literal

from fastapi import APIRouter, Depends

from api import assemble
from api.auth import current_user
from api.deps import get_conn_dep
from api.ids import uid
from api.schemas import EventOut
from repo import events

router = APIRouter()


@router.get("/audit")
def audit(
    entity_type: Literal["change", "revision", "user", "document"],
    entity_id: str,
    _user: dict = Depends(current_user),
    conn=Depends(get_conn_dep),
) -> list[EventOut]:
    return assemble.event_outs(conn, events.for_entity(conn, entity_type, uid(entity_id)))
