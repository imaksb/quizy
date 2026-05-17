from pydantic import BaseModel, Field

from app.schemas.quiz import QuestionCreate, QuestionDetail


class AIQuestionGenerationRequest(BaseModel):
    user_prompt: str = Field(min_length=1, max_length=4000)
    questions_count: int = Field(default=5, ge=1, le=10)


class AIQuestionGenerationResponse(BaseModel):
    quiz_id: str
    questions: list[QuestionDetail]


class AIGeneratedQuestions(BaseModel):
    questions: list[QuestionCreate] = Field(min_length=1, max_length=10)
