from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class UserRole(Enum):
    USER = "user"
    ADMIN = "admin"

class UserInfo(BaseModel):
    email: str
    name: str
    picture: str | None
    email_verified: bool

class UserDetail(UserInfo):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    role: UserRole
