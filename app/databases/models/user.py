import uuid
from typing import TYPE_CHECKING

from pydantic import UUID4
from sqlalchemy import BOOLEAN, UUID, VARCHAR, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.databases.models.base import Base, TableNameMixin, TimeoutMixin
from app.schemas.user import UserRole

if TYPE_CHECKING:
    from app.databases.models.quiz import Quiz, QuizSession, SessionParticipant


class User(Base, TableNameMixin, TimeoutMixin):
    id: Mapped[UUID4] = mapped_column(
        UUID, primary_key=True, default=uuid.uuid4, unique=True
    )
    email: Mapped[str] = mapped_column(VARCHAR(255), unique=True)
    name: Mapped[str] = mapped_column(VARCHAR(255))
    picture: Mapped[str | None] = mapped_column(VARCHAR(2048), nullable=True)
    email_verified: Mapped[bool | None] = mapped_column(BOOLEAN, nullable=True)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole), nullable=False, default=UserRole.USER
    )
    is_active: Mapped[bool] = mapped_column(BOOLEAN, default=True)

    quizzes: Mapped[list["Quiz"]] = relationship(back_populates="owner")
    owned_quiz_sessions: Mapped[list["QuizSession"]] = relationship(
        back_populates="owner"
    )
    session_participations: Mapped[list["SessionParticipant"]] = relationship(
        back_populates="user"
    )
