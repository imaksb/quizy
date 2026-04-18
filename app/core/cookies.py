from typing import Any

from starlette.responses import Response

from app.core.settings import settings
from app.schemas.auth import JWTTokens


COOKIE_ACCESS_TOKEN = "ACCESS_TOKEN"
COOKIE_REFRESH_TOKEN = "REFRESH_TOKEN"


def _base_cookie_kwargs() -> dict[str, Any]:
    """
    Cookie attributes shared by set/delete.

    In development (cross-port on localhost) the cookie must be host-only
    (no explicit domain) so the browser keeps a single `localhost` cookie
    that is visible from both the API (:8000) and the UI (:3000).
    """
    is_dev = settings.ENVIRONMENT == "development"

    kwargs: dict[str, Any] = {
        "path": "/",
        "secure": not is_dev,
        "samesite": "lax" if is_dev else "none",
    }
    if not is_dev:
        kwargs["domain"] = settings.DOMAIN
    return kwargs


def set_auth_cookies(response: Response, tokens: JWTTokens) -> None:
    base = _base_cookie_kwargs()

    response.set_cookie(
        key=COOKIE_ACCESS_TOKEN,
        value=tokens.access_token,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        httponly=False,
        **base,
    )
    response.set_cookie(
        key=COOKIE_REFRESH_TOKEN,
        value=tokens.refresh_token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_MINUTES * 60,
        httponly=True,
        **base,
    )


def clear_auth_cookies(response: Response) -> None:
    base = _base_cookie_kwargs()
    base.pop("samesite", None)
    base.pop("secure", None)

    response.delete_cookie(key=COOKIE_ACCESS_TOKEN, **base)
    response.delete_cookie(key=COOKIE_REFRESH_TOKEN, **base)
