from fastapi import APIRouter

from app.dependencies.database import SessionDep
from app.dependencies.redis_server import RedisDep
from app.dependencies.user_validation import CurrentAdminUser
from app.schemas.ai import AIQuestionGenerationRequest, AIQuestionGenerationResponse
from app.schemas.quiz import QuestionDetail
from app.services.ai_generation_service import AIQuestionGenerationService

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post(
    "/quizzes/{quiz_id}/questions",
    response_model=AIQuestionGenerationResponse,
    status_code=201,
)
async def generate_quiz_questions(
    quiz_id: str,
    data: AIQuestionGenerationRequest,
    session: SessionDep,
    redis: RedisDep,
    admin_user: CurrentAdminUser,
) -> AIQuestionGenerationResponse:
    service = AIQuestionGenerationService(session=session, redis=redis)
    questions = await service.generate_questions(
        quiz_id=quiz_id,
        data=data,
        user=admin_user,
    )
    return AIQuestionGenerationResponse(
        quiz_id=quiz_id,
        questions=[
            QuestionDetail.model_validate(question)
            for question in questions
        ],
    )
