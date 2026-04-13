import secrets
from datetime import datetime, timedelta
import jwt
from argon2 import PasswordHasher
from fastapi import HTTPException
from pydantic import ValidationError
from starlette import status
from uuid import uuid4
from app.core.settings import settings
from app.schemas.auth import JWTPayload, JWTToken, JWTTokens
from app.schemas.user import UserRole
from app.utils.exceptions import InvalidCredentials

ALGORITHM = "HS256"
context = PasswordHasher()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return context.verify(hashed_password, plain_password)


def get_hash_password(password: str) -> str:
    return context.hash(password)

def create_jwt_token(email: str, role: UserRole, token_type: str = "bearer") -> JWTToken:
    expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    expire = datetime.now() + expires_delta

    payload = JWTPayload(
        role=role,
        email=email,
        exp=expire,
        token_type=token_type,
        jti=str(uuid4()),
    )

    payload_dict = payload.model_dump()
    payload_dict['role'] = role.value

    encoded_jwt = jwt.encode(
    payload_dict, settings.AUTH_SECRET_KEY, algorithm=ALGORITHM
    )


    return JWTToken(access_token=encoded_jwt, token_type=token_type)


def get_pair_tokens(email: str, role: UserRole) -> JWTTokens:
    access_token = create_jwt_token(email=email, role=role, token_type="access")
    refresh_token = create_jwt_token(email=email, role=role, token_type="refresh")

    return JWTTokens(
        access_token=access_token.access_token, refresh_token=refresh_token.access_token
    )


def get_new_access_token_with_refresh(payload: JWTPayload) -> JWTTokens:
    if payload.token_type != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type"
        )

    return get_pair_tokens(email=payload.email, role=payload.role)


def decode_auth_jwt_token(
    token: str,
    secret_key: str = settings.AUTH_SECRET_KEY,
) -> JWTPayload:
    try:
        payload = jwt.decode(
            token, secret_key, algorithms=[ALGORITHM], leeway=60
        )
        payload.setdefault("token_type", "access")
        payload.setdefault("jti", "")

        return JWTPayload(**payload)
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, ValidationError):
        raise InvalidCredentials()

def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)