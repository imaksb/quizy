from fastapi import APIRouter
from starlette.responses import RedirectResponse

from app.core.cookies import set_auth_cookies
from app.core.google_oauth import get_google_redirect_link
from app.core.settings import settings
from app.dependencies.database import SessionDep
from app.schemas.auth import JWTTokens
from app.services.auth_service import AuthService


router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/")
async def auth() -> RedirectResponse:
    """
    Redirect the user to Google OAuth2.
    """
    return RedirectResponse(url=get_google_redirect_link())


@router.get("/callback")
async def auth_callback(session: SessionDep, code: str) -> RedirectResponse:
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
async def auth_refresh(refresh_token: str, session: SessionDep) -> JWTTokens:
    return await (AuthService(session=session).
                  refresh(refresh_token=refresh_token))
