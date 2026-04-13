from pydantic import BaseModel
from datetime import datetime

from app.schemas.user import UserRole

import urllib.parse
from enum import Enum

from fastapi import HTTPException

class OriginType(str, Enum):
    ADMIN = "admin"
    GAME = "game"

class AuthState(BaseModel):
    origin: OriginType
    game_id: str | None = None

    def encode(self) -> str:
        return urllib.parse.quote(self.model_dump_json())

    @classmethod
    def decode(cls, state_str: str) -> "AuthState":
        try:
            decoded = urllib.parse.unquote(state_str)
            return cls.model_validate_json(decoded)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid state")


class JWTPayload(BaseModel):
    jti: str
    email: str
    exp: datetime
    role: UserRole
    token_type: str


class JWTToken(BaseModel):
    access_token: str
    token_type: str


class JWTTokens(BaseModel):
    access_token: str
    refresh_token: str
