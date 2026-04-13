from typing import Annotated

from fastapi.params import Depends

from app.schemas.user import UserDetail
from app.services.auth_service import AuthService

CurrentUser = Annotated[UserDetail, Depends(AuthService.get_current_user)]
    