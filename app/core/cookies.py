from urllib.parse import urlsplit
from starlette.responses import Response

from app.core.settings import settings
from app.schemas.types import CookieKwargs
from app.schemas.auth import JWTTokens


COOKIE_ACCESS_TOKEN = "ACCESS_TOKEN"
COOKIE_REFRESH_TOKEN = "REFRESH_TOKEN"


def _normalize_host(value: str) -> str | None:
    raw = value.strip()
    if not raw:
        return None
    if "://" not in raw:
        raw = f"https://{raw}"
    host = urlsplit(raw).hostname
    return host.lower() if host else None


def _common_cookie_domain(hosts: list[str]) -> str | None:
    parts = [host.split(".") for host in hosts if host]
    if not parts:
        return None
    common_suffix: list[str] = []
    for labels in zip(*(reversed(host_part) for host_part in parts), strict=False):
        if len(set(labels)) != 1:
            break
        common_suffix.append(labels[0])
    if len(common_suffix) < 2:
        return None
    return ".".join(reversed(common_suffix))


def _resolve_cookie_domain() -> str | None:
    configured = _normalize_host(settings.DOMAIN)
    frontend_admin_host = _normalize_host(settings.FRONTEND_ADMIN_URL)
    frontend_client_host = _normalize_host(settings.FRONTEND_CLIENT_URL)

    candidates = [
        host
        for host in [configured, frontend_admin_host, frontend_client_host]
        if host and host != "localhost"
    ]
    shared_domain = _common_cookie_domain(candidates)
    if shared_domain:
        print(
            "[cookie-debug] domain resolve:",
            {
                "configured": configured,
                "frontend_admin": frontend_admin_host,
                "frontend_client": frontend_client_host,
                "selected": shared_domain,
            },
        )
        return shared_domain
    if configured and configured != "localhost":
        print(
            "[cookie-debug] domain resolve:",
            {
                "configured": configured,
                "frontend_admin": frontend_admin_host,
                "frontend_client": frontend_client_host,
                "selected": configured,
            },
        )
        return configured
    print(
        "[cookie-debug] domain resolve:",
        {
            "configured": configured,
            "frontend_admin": frontend_admin_host,
            "frontend_client": frontend_client_host,
            "selected": None,
        },
    )
    return None


def _base_cookie_kwargs() -> CookieKwargs:
    """
    Cookie attributes shared by set/delete.

    In development (cross-port on localhost) the cookie must be host-only
    (no explicit domain) so the browser keeps a single `localhost` cookie
    that is visible from both the API (:8000) and the UI (:3000).
    """
    is_dev = settings.ENVIRONMENT == "development"

    kwargs: CookieKwargs = {
        "path": "/",
        "secure": not is_dev,
        "samesite": "lax" if is_dev else "none",
    }
    if not is_dev:
        domain = _resolve_cookie_domain()
        if domain:
            kwargs["domain"] = domain
    return kwargs


def set_auth_cookies(response: Response, tokens: JWTTokens) -> None:
    base = _base_cookie_kwargs()
    access_max_age = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    refresh_max_age = settings.REFRESH_TOKEN_EXPIRE_MINUTES * 60

    print(
        "[cookie-debug] set_auth_cookies input:",
        {
            "environment": settings.ENVIRONMENT,
            "domain_setting": settings.DOMAIN,
            "cookie_base": base,
            "access_max_age": access_max_age,
            "refresh_max_age": refresh_max_age,
            "access_token_preview": f"{tokens.access_token[:12]}...",
            "refresh_token_preview": f"{tokens.refresh_token[:12]}...",
        },
    )

    response.set_cookie(
        key=COOKIE_ACCESS_TOKEN,
        value=tokens.access_token,
        max_age=access_max_age,
        httponly=False,
        **base,
    )
    response.set_cookie(
        key=COOKIE_REFRESH_TOKEN,
        value=tokens.refresh_token,
        max_age=refresh_max_age,
        httponly=True,
        **base,
    )

    set_cookie_headers = [
        value.decode("latin-1")
        for key, value in response.raw_headers
        if key.lower() == b"set-cookie"
    ]
    print("[cookie-debug] response set-cookie headers:", set_cookie_headers)
