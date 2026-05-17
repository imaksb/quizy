from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Response
from starlette.responses import RedirectResponse

from app.core.cookies import COOKIE_REFRESH_TOKEN, set_auth_cookies
from app.core.google_oauth import get_google_redirect_link
from app.core.settings import settings
from app.dependencies.database import SessionDep
from app.schemas.auth import JWTTokens
from app.services.auth_service import AuthService
from app.utils.rate_limit import rate_limit

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/")
async def auth(
    _: None = Depends(rate_limit("auth:start", limit=20))
) -> RedirectResponse:
    """
    Redirect the user to Google OAuth2.
    """
    return RedirectResponse(url=get_google_redirect_link())


@router.get("/callback")
async def auth_callback(
    session: SessionDep,
    code: str,
    _: None = Depends(rate_limit("auth:callback", limit=20)),
) -> RedirectResponse:
    """
    Google redirects here with an authorization `code`. We exchange it for
    JWT tokens, drop them into cookies on the shared host and bounce the
    browser back to the admin UI.
    """
    auth_service = AuthService(session=session)
    tokens = await auth_service.login(code=code)

    response = RedirectResponse(url=f"{settings.FRONTEND_ADMIN_URL}/dashboard")
    set_auth_cookies(response, tokens)
    return response


@router.get("/refresh", response_model=JWTTokens)
async def auth_refresh(
    session: SessionDep,
    response: Response,
    refresh_token: Annotated[str, Cookie(alias=COOKIE_REFRESH_TOKEN)],
    _: None = Depends(rate_limit("auth:refresh", limit=30)),
) -> JWTTokens:
    tokens = await AuthService(session=session).refresh(refresh_token=refresh_token)
    set_auth_cookies(response, tokens)
    return tokens
