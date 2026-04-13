from fastapi import APIRouter
from fastapi.params import Depends, Query
from starlette.responses import RedirectResponse

from app.core.google_oauth import get_google_redirect_link
from app.dependencies.database import SessionDep
from app.schemas.auth import JWTTokens
from app.services.auth_service import AuthService


router = APIRouter(prefix="/auth", tags=["auth"])

@router.get("/")
async def auth() -> RedirectResponse:
    """
    Redirect the user to Google OAuth2
    :return:
    """
    return RedirectResponse(url=get_google_redirect_link())


@router.get("/callback", response_model=JWTTokens)
async def auth_callback(session: SessionDep, code: str) -> JWTTokens:
    auth_service = AuthService(session=session)
    return await auth_service.login(code=code)


@router.get("/refresh", response_model=JWTTokens)
async def auth_refresh(refresh_token: str, session: SessionDep) -> JWTTokens:
    return await (AuthService(session=session).
                  refresh(refresh_token=refresh_token))
