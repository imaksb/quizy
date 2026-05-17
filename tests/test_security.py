from types import SimpleNamespace
from uuid import uuid4

import jwt
import pytest

from app.core.security import (
    ALGORITHM,
    create_jwt_token,
    decode_auth_jwt_token,
    get_new_access_token_with_refresh,
)
from app.core.settings import Settings, settings
from app.schemas.user import UserRole
from app.services.auth_service import AuthService
from app.utils.exceptions import InvalidCredentials


def test_refresh_token_uses_refresh_expiry() -> None:
    access = decode_auth_jwt_token(
        create_jwt_token("admin@example.com", UserRole.ADMIN, "access").access_token
    )
    refresh = decode_auth_jwt_token(
        create_jwt_token("admin@example.com", UserRole.ADMIN, "refresh").access_token
    )

    assert access.token_type == "access"
    assert refresh.token_type == "refresh"
    assert refresh.exp > access.exp


def test_legacy_token_without_token_type_is_rejected() -> None:
    token = jwt.encode(
        {
            "email": "admin@example.com",
            "role": UserRole.ADMIN.value,
            "exp": 4_102_444_800,
            "jti": str(uuid4()),
        },
        settings.AUTH_SECRET_KEY,
        algorithm=ALGORITHM,
    )

    with pytest.raises(InvalidCredentials):
        decode_auth_jwt_token(token)


def test_access_token_cannot_be_used_for_refresh() -> None:
    payload = decode_auth_jwt_token(
        create_jwt_token("admin@example.com", UserRole.ADMIN, "access").access_token
    )

    with pytest.raises(Exception) as exc_info:
        get_new_access_token_with_refresh(payload)

    assert getattr(exc_info.value, "status_code", None) == 401


@pytest.mark.asyncio
async def test_bearer_refresh_token_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_get_user_by_email(self: AuthService, email: str):
        return SimpleNamespace(
            id=uuid4(),
            email=email,
            name="Admin",
            picture=None,
            email_verified=True,
            role=UserRole.ADMIN,
            is_active=True,
        )

    monkeypatch.setattr(AuthService, "_get_user_by_email", fake_get_user_by_email)
    refresh_token = create_jwt_token(
        "admin@example.com",
        UserRole.ADMIN,
        "refresh",
    ).access_token
    credentials = SimpleNamespace(credentials=refresh_token)

    with pytest.raises(InvalidCredentials):
        await AuthService.get_current_user(credentials, session=object())


def test_production_cors_does_not_allow_localhost_regex_by_default() -> None:
    production_settings = Settings(
        AUTH_SECRET_KEY="secret",
        ENVIRONMENT="production",
        FAKE_HASH="hash",
        POSTGRES_USER="quizy",
        POSTGRES_DB="quizy",
        POSTGRES_PASSWORD="quizy",
        POSTGRES_HOST="db",
        POSTGRES_PORT=5432,
        GOOGLE_CLIENT_SECRET="secret",
        GOOGLE_CLIENT_ID="client",
        GOOGLE_REDIRECT_URI="https://api.example.com/auth/callback",
        FRONTEND_ADMIN_URL="https://admin.example.com",
        FRONTEND_CLIENT_URL="https://play.example.com",
        OPENAPI_SWAGGER_PASSWORD="docs-password",
    )

    assert production_settings.cors_allowed_origin_regex is None
