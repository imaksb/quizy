from typing import Annotated

from fastapi import HTTPException
from fastapi.params import Depends
from starlette import status

from app.schemas.user import UserDetail
from app.schemas.user import UserRole
from app.services.auth_service import AuthService

CurrentUser = Annotated[UserDetail, Depends(AuthService.get_current_user)]


async def require_admin(user: CurrentUser) -> UserDetail:
    if user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user


CurrentAdminUser = Annotated[UserDetail, Depends(require_admin)]
