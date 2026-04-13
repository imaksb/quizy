import uuid
from pydantic import UUID4
from sqlalchemy import BOOLEAN, UUID, VARCHAR, Enum
from sqlalchemy.orm import Mapped, mapped_column

from app.databases.models.base import Base, TableNameMixin, TimeoutMixin
from app.schemas.user import UserRole


class User(Base, TableNameMixin, TimeoutMixin):
    id: Mapped[UUID4] = mapped_column(
        UUID, primary_key=True, default=uuid.uuid4, unique=True
    )
    email: Mapped[str] = mapped_column(VARCHAR(50), unique=True)
    name: Mapped[str] = mapped_column(VARCHAR(50), unique=True)
    picture: Mapped[str] = mapped_column(VARCHAR(255), unique=True, nullable=True)
    email_verified: Mapped[bool] = mapped_column(BOOLEAN, unique=True, nullable=True)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), nullable=False, default=UserRole.USER)
    is_active: Mapped[bool] = mapped_column(BOOLEAN, default=True)
