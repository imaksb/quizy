from fastapi import APIRouter

from app.dependencies.user_validation import CurrentUser
from app.schemas.user import UserDetail

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/me", response_model=UserDetail)
async def get_users(user: CurrentUser) -> UserDetail:
    return user

