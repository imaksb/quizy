import enum
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class QuestionType(enum.Enum):
    SINGLE_ANSWER = "single_answer"
    MULTIPLE_ANSWER = "multiple_answer"


class SessionStatus(enum.Enum):
    CREATED = "created"
    LOBBY = "lobby"
    LIVE = "live"
    PAUSED = "paused"
    FINISHED = "finished"
    CANCELLED = "cancelled"


class ParticipantStatus(enum.Enum):
    JOINED = "joined"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    FINISHED = "finished"
    DISCONNECTED = "disconnected"


class SessionQuestionStatus(enum.Enum):
    PENDING = "pending"
    ACTIVE = "active"
    CLOSED = "closed"


class QuizBase(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1, max_length=1000)
    is_published: bool = False
    default_question_time: int = Field(gt=0)


class QuizCreate(QuizBase):
    pass


class QuizUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, min_length=1, max_length=1000)
    is_published: bool | None = None
    default_question_time: int | None = Field(default=None, gt=0)


class QuizDetail(QuizBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    owner_id: UUID
    created_at: datetime
    updated_at: datetime


class QuizListResponse(BaseModel):
    items: list[QuizDetail]
    total: int
    page: int
    page_size: int


class QuestionBase(BaseModel):
    question_text: str = Field(min_length=1, max_length=1000)
    question_type: QuestionType
    order_index: int = Field(ge=0)
    answer_time: int | None = Field(default=None, gt=0)
    points_for_correct_answer: int = 1
    points_for_incorrect_answer: int = 0
    hint: str | None = Field(default=None, max_length=1000)
    image_url: str | None = Field(default=None, max_length=2048)


class QuestionCreate(QuestionBase):
    answers: list["AnswerOptionCreate"] = Field(min_length=1)


class QuestionUpdate(BaseModel):
    question_text: str | None = Field(default=None, min_length=1, max_length=1000)
    question_type: QuestionType | None = None
    order_index: int | None = Field(default=None, ge=0)
    answer_time: int | None = Field(default=None, gt=0)
    points_for_correct_answer: int | None = None
    points_for_incorrect_answer: int | None = None
    hint: str | None = Field(default=None, max_length=1000)
    image_url: str | None = Field(default=None, max_length=2048)


class QuestionDetail(QuestionBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    quiz_id: UUID
    created_at: datetime
    updated_at: datetime
    answers: list["AnswerOptionDetail"]


class AnswerOptionCreate(BaseModel):
    answer_text: str = Field(min_length=1, max_length=500)
    is_correct: bool = False


class AnswerOptionUpdate(BaseModel):
    answer_text: str | None = Field(default=None, min_length=1, max_length=500)
    is_correct: bool | None = None


class AnswerOptionDetail(AnswerOptionCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime


class QuizWithQuestionsDetail(QuizDetail):
    questions: list[QuestionDetail]


QuestionCreate.model_rebuild()
QuestionDetail.model_rebuild()
QuizWithQuestionsDetail.model_rebuild()
