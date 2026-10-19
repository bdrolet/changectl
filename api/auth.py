import os

from fastapi import Depends, HTTPException, Request

from api.deps import get_conn_dep
from clients.google_id_token import verify_id_token
from repo import events, users


def _bearer(request: Request) -> str:
    parts = request.headers.get("Authorization", "").split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(401, detail="missing_bearer")
    return parts[1]


def current_user(request: Request, conn=Depends(get_conn_dep)) -> dict:
    dev_email = os.environ.get("CHANGECTL_DEV_USER_EMAIL")
    if not os.environ.get("K_SERVICE") and dev_email:
        email, sub = dev_email, "dev"
    else:
        token = _bearer(request)
        try:
            claims = verify_id_token(token, os.environ.get("GOOGLE_OAUTH_CLIENT_ID", ""))
        except ValueError:
            raise HTTPException(401, detail="invalid_token") from None
        if not claims.email_verified:
            raise HTTPException(401, detail="email_unverified")
        email, sub = claims.email, claims.sub

    user = users.by_email(conn, email)
    if user is None or user["deactivated_at"] is not None:
        raise HTTPException(403, detail="not_invited")
    if user["google_sub"] is None:
        users.set_google_sub(conn, str(user["id"]), sub)
        events.record(
            conn,
            actor_user_id=user["id"],
            entity_type="user",
            entity_id=user["id"],
            action="user.first_sign_in",
            detail={"email": user["email"]},
        )
        user = {**user, "google_sub": sub}
    elif user["google_sub"] != sub:
        raise HTTPException(403, detail="identity_mismatch")
    request.state.google_sub = sub
    return user


def require_doc_manager(user: dict = Depends(current_user)) -> dict:
    if not user["is_doc_manager"]:
        raise HTTPException(403, detail="doc_manager_required")
    return user
