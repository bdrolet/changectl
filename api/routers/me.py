from fastapi import APIRouter, Depends

from api.auth import current_user
from api.schemas import UserOut, user_out

router = APIRouter()


@router.get("/me")
def me(user: dict = Depends(current_user)) -> UserOut:
    return user_out(user)
