import uuid
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    BOOLEAN,
    JSON,
    TIMESTAMP,
    UUID as SAUUID,
    CheckConstraint,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.databases.models.base import Base, TableNameMixin, TimeoutMixin
from app.schemas.quiz import ParticipantStatus, QuestionType, SessionQuestionStatus, SessionStatus

if TYPE_CHECKING:
    from app.databases.models.user import User

class Quiz(Base, TableNameMixin, TimeoutMixin):
    id: Mapped[UUID] = mapped_column(
        SAUUID, primary_key=True, default=uuid.uuid4, unique=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(String(1000), nullable=False)
    is_published: Mapped[bool] = mapped_column(BOOLEAN, default=False, nullable=False)
    default_question_time: Mapped[int] = mapped_column(Integer, nullable=False)
    owner_id: Mapped[UUID] = mapped_column(
        SAUUID, ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True
    )

    owner: Mapped["User"] = relationship(back_populates="quizzes")
    questions: Mapped[list["Question"]] = relationship(
        back_populates="quiz",
        cascade="all, delete-orphan",
        order_by="Question.order_index",
    )
    sessions: Mapped[list["QuizSession"]] = relationship(
        back_populates="quiz",
        cascade="all, delete-orphan",
    )


class Question(Base, TableNameMixin, TimeoutMixin):
    __table_args__ = (
        UniqueConstraint("quiz_id", "order_index", name="uq_question_quiz_order_index"),
    )

    id: Mapped[UUID] = mapped_column(
        SAUUID, primary_key=True, default=uuid.uuid4, unique=True
    )
    quiz_id: Mapped[UUID] = mapped_column(
        SAUUID, ForeignKey("quiz.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question_text: Mapped[str] = mapped_column(String(1000), nullable=False)
    question_type: Mapped[QuestionType] = mapped_column(
        Enum(QuestionType), nullable=False
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    answer_time: Mapped[int | None] = mapped_column(Integer, nullable=True)
    points_for_correct_answer: Mapped[int] = mapped_column(
        Integer, default=1, nullable=False
    )
    points_for_incorrect_answer: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    hint: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)

    quiz: Mapped["Quiz"] = relationship(back_populates="questions")
    answers: Mapped[list["AnswerOption"]] = relationship(
        back_populates="question",
        cascade="all, delete-orphan",
    )
    participant_answers: Mapped[list["ParticipantAnswer"]] = relationship(
        back_populates="question"
    )
    session_question_states: Mapped[list["SessionQuestionState"]] = relationship(
        back_populates="question",
        cascade="all, delete-orphan",
    )


class AnswerOption(Base, TableNameMixin):
    id: Mapped[UUID] = mapped_column(
        SAUUID, primary_key=True, default=uuid.uuid4, unique=True
    )
    question_id: Mapped[UUID] = mapped_column(
        SAUUID,
        ForeignKey("question.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    answer_text: Mapped[str] = mapped_column(String(500), nullable=False)
    is_correct: Mapped[bool] = mapped_column(BOOLEAN, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP, server_default=func.now(), nullable=False
    )

    question: Mapped["Question"] = relationship(back_populates="answers")
    participant_answer_links: Mapped[list["ParticipantAnswerOption"]] = relationship(
        back_populates="answer_option",
        cascade="all, delete-orphan",
    )


class QuizSession(Base, TableNameMixin, TimeoutMixin):
    id: Mapped[UUID] = mapped_column(
        SAUUID, primary_key=True, default=uuid.uuid4, unique=True
    )
    quiz_id: Mapped[UUID] = mapped_column(
        SAUUID, ForeignKey("quiz.id", ondelete="CASCADE"), nullable=False, index=True
    )
    owner_id: Mapped[UUID] = mapped_column(
        SAUUID, ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[SessionStatus] = mapped_column(
        Enum(SessionStatus), default=SessionStatus.CREATED, nullable=False
    )
    join_code: Mapped[str | None] = mapped_column(
        String(32), nullable=True, unique=True, index=True
    )
    access_link_token: Mapped[str] = mapped_column(String(255), nullable=False)
    current_question_index: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(TIMESTAMP, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(TIMESTAMP, nullable=True)

    quiz: Mapped["Quiz"] = relationship(back_populates="sessions")
    owner: Mapped["User"] = relationship(back_populates="owned_quiz_sessions")
    participants: Mapped[list["SessionParticipant"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )
    participant_answers: Mapped[list["ParticipantAnswer"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )
    question_states: Mapped[list["SessionQuestionState"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="SessionQuestionState.question_order_index",
    )
    result: Mapped["SessionResult | None"] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )


class SessionParticipant(Base, TableNameMixin):
    __table_args__ = (
        UniqueConstraint(
            "session_id",
            "guest_token",
            name="uq_sessionparticipant_session_guest_token",
        ),
        CheckConstraint(
            """
            (
                user_id IS NOT NULL
                AND guest_name IS NULL
                AND guest_token IS NULL
            )
            OR
            (
                user_id IS NULL
                AND guest_name IS NOT NULL
                AND guest_token IS NOT NULL
            )
            """,
            name="ck_sessionparticipant_user_or_guest",
        ),
        Index(
            "ix_sessionparticipant_session_id_host",
            "session_id",
            postgresql_where=text("is_host = true"),
        ),
    )

    id: Mapped[UUID] = mapped_column(
        SAUUID, primary_key=True, default=uuid.uuid4, unique=True
    )
    session_id: Mapped[UUID] = mapped_column(
        SAUUID,
        ForeignKey("quizsession.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[UUID | None] = mapped_column(
        SAUUID, ForeignKey("user.id", ondelete="SET NULL"), nullable=True, index=True
    )
    guest_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    guest_token: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[ParticipantStatus] = mapped_column(
        Enum(ParticipantStatus), default=ParticipantStatus.JOINED, nullable=False
    )
    score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    joined_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(TIMESTAMP, nullable=True)
    is_host: Mapped[bool] = mapped_column(BOOLEAN, default=False, nullable=False)

    session: Mapped["QuizSession"] = relationship(back_populates="participants")
    user: Mapped["User | None"] = relationship(back_populates="session_participations")
    answers: Mapped[list["ParticipantAnswer"]] = relationship(
        back_populates="participant",
        cascade="all, delete-orphan",
    )


class ParticipantAnswer(Base, TableNameMixin):
    __table_args__ = (
        UniqueConstraint(
            "session_id",
            "participant_id",
            "question_id",
            name="uq_participantanswer_session_participant_question",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        SAUUID, primary_key=True, default=uuid.uuid4, unique=True
    )
    session_id: Mapped[UUID] = mapped_column(
        SAUUID,
        ForeignKey("quizsession.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    participant_id: Mapped[UUID] = mapped_column(
        SAUUID,
        ForeignKey("sessionparticipant.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    question_id: Mapped[UUID] = mapped_column(
        SAUUID,
        ForeignKey("question.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    answered_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False)
    is_correct: Mapped[bool] = mapped_column(BOOLEAN, nullable=False)
    points_awarded: Mapped[int] = mapped_column(Integer, nullable=False)
    response_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    session: Mapped["QuizSession"] = relationship(back_populates="participant_answers")
    participant: Mapped["SessionParticipant"] = relationship(back_populates="answers")
    question: Mapped["Question"] = relationship(back_populates="participant_answers")
    selected_options: Mapped[list["ParticipantAnswerOption"]] = relationship(
        back_populates="participant_answer",
        cascade="all, delete-orphan",
    )


class ParticipantAnswerOption(Base):
    __tablename__ = "participant_answer_option"
    __table_args__ = (
        UniqueConstraint(
            "participant_answer_id",
            "answer_option_id",
            name="uq_participantansweroption_answer_option",
        ),
    )

    participant_answer_id: Mapped[UUID] = mapped_column(
        SAUUID,
        ForeignKey("participantanswer.id", ondelete="CASCADE"),
        primary_key=True,
    )
    answer_option_id: Mapped[UUID] = mapped_column(
        SAUUID,
        ForeignKey("answeroption.id", ondelete="CASCADE"),
        primary_key=True,
    )

    participant_answer: Mapped["ParticipantAnswer"] = relationship(
        back_populates="selected_options"
    )
    answer_option: Mapped["AnswerOption"] = relationship(
        back_populates="participant_answer_links"
    )


class SessionQuestionState(Base, TableNameMixin):
    __table_args__ = (
        UniqueConstraint(
            "session_id",
            "question_id",
            name="uq_sessionquestionstate_session_question",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        SAUUID, primary_key=True, default=uuid.uuid4, unique=True
    )
    session_id: Mapped[UUID] = mapped_column(
        SAUUID,
        ForeignKey("quizsession.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    question_id: Mapped[UUID] = mapped_column(
        SAUUID,
        ForeignKey("question.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    question_order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[SessionQuestionStatus] = mapped_column(
        Enum(SessionQuestionStatus),
        default=SessionQuestionStatus.PENDING,
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(TIMESTAMP, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP, nullable=True)
    time_limit_seconds: Mapped[int] = mapped_column(Integer, nullable=False)

    session: Mapped["QuizSession"] = relationship(back_populates="question_states")
    question: Mapped["Question"] = relationship(back_populates="session_question_states")


class SessionResult(Base, TableNameMixin):
    id: Mapped[UUID] = mapped_column(
        SAUUID, primary_key=True, default=uuid.uuid4, unique=True
    )
    session_id: Mapped[UUID] = mapped_column(
        SAUUID,
        ForeignKey("quizsession.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    quiz_id: Mapped[UUID] = mapped_column(
        SAUUID, ForeignKey("quiz.id", ondelete="CASCADE"), nullable=False, index=True
    )
    owner_id: Mapped[UUID] = mapped_column(
        SAUUID, ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    started_at: Mapped[datetime | None] = mapped_column(TIMESTAMP, nullable=True)
    finished_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False)
    total_players: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP, server_default=func.now(), nullable=False
    )

    session: Mapped["QuizSession"] = relationship(back_populates="result")
    players: Mapped[list["SessionPlayerResult"]] = relationship(
        back_populates="session_result",
        cascade="all, delete-orphan",
        order_by="SessionPlayerResult.final_rank",
    )


class SessionPlayerResult(Base, TableNameMixin):
    id: Mapped[UUID] = mapped_column(
        SAUUID, primary_key=True, default=uuid.uuid4, unique=True
    )
    session_result_id: Mapped[UUID] = mapped_column(
        SAUUID,
        ForeignKey("sessionresult.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    participant_id: Mapped[UUID] = mapped_column(SAUUID, nullable=False, index=True)
    guest_name: Mapped[str] = mapped_column(String(255), nullable=False)
    final_score: Mapped[int] = mapped_column(Integer, nullable=False)
    final_rank: Mapped[int] = mapped_column(Integer, nullable=False)

    session_result: Mapped["SessionResult"] = relationship(back_populates="players")
    answers: Mapped[list["SessionAnswerResult"]] = relationship(
        back_populates="player_result",
        cascade="all, delete-orphan",
    )


class SessionAnswerResult(Base, TableNameMixin):
    id: Mapped[UUID] = mapped_column(
        SAUUID, primary_key=True, default=uuid.uuid4, unique=True
    )
    player_result_id: Mapped[UUID] = mapped_column(
        SAUUID,
        ForeignKey("sessionplayerresult.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    question_id: Mapped[UUID] = mapped_column(
        SAUUID, ForeignKey("question.id", ondelete="SET NULL"), nullable=True, index=True
    )
    selected_answer_option_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    is_correct: Mapped[bool] = mapped_column(BOOLEAN, nullable=False)
    points_awarded: Mapped[int] = mapped_column(Integer, nullable=False)
    answered_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False)

    player_result: Mapped["SessionPlayerResult"] = relationship(back_populates="answers")
