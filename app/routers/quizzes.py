from fastapi import APIRouter, Query

from app.dependencies.database import SessionDep
from app.dependencies.user_validation import CurrentAdminUser
from app.schemas.quiz import (
    AnswerOptionDetail,
    AnswerOptionUpdate,
    QuestionCreate,
    QuestionDetail,
    QuestionUpdate,
    QuizCreate,
    QuizDetail,
    QuizListResponse,
    QuizUpdate,
    QuizWithQuestionsDetail,
)
from app.services.quiz_service import QuizService

router = APIRouter(prefix="/quizzes", tags=["quizzes"])


@router.post("/", response_model=QuizDetail, status_code=201)
async def create_quiz(
    data: QuizCreate,
    session: SessionDep,
    admin_user: CurrentAdminUser,
) -> QuizDetail:
    quiz_service = QuizService(session=session)
    quiz = await quiz_service.create_quiz(data=data, owner=admin_user)
    return QuizDetail.model_validate(quiz)


@router.get("/", response_model=QuizListResponse)
async def get_quizzes(
    session: SessionDep,
    admin_user: CurrentAdminUser,  # noqa: ARG001
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
) -> QuizListResponse:
    quiz_service = QuizService(session=session)
    return await quiz_service.get_quizzes(page=page, page_size=page_size)


@router.get("/{quiz_id}", response_model=QuizWithQuestionsDetail)
async def get_quiz(
    quiz_id: str,
    session: SessionDep,
    admin_user: CurrentAdminUser,  # noqa: ARG001
) -> QuizWithQuestionsDetail:
    quiz_service = QuizService(session=session)
    quiz = await quiz_service.get_quiz(quiz_id=quiz_id)
    return QuizWithQuestionsDetail.model_validate(quiz)


@router.patch("/{quiz_id}", response_model=QuizDetail)
async def update_quiz(
    quiz_id: str,
    data: QuizUpdate,
    session: SessionDep,
    admin_user: CurrentAdminUser,  # noqa: ARG001
) -> QuizDetail:
    quiz_service = QuizService(session=session)
    quiz = await quiz_service.update_quiz(quiz_id=quiz_id, data=data)
    return QuizDetail.model_validate(quiz)


@router.delete("/{quiz_id}", response_model=QuizDetail)
async def delete_quiz(
    quiz_id: str,
    session: SessionDep,
    admin_user: CurrentAdminUser,  # noqa: ARG001
) -> QuizDetail:
    quiz_service = QuizService(session=session)
    quiz = await quiz_service.delete_quiz(quiz_id=quiz_id)
    return QuizDetail.model_validate(quiz)


@router.post("/{quiz_id}/questions", response_model=QuestionDetail, status_code=201)
async def create_question(
    quiz_id: str,
    data: QuestionCreate,
    session: SessionDep,
    admin_user: CurrentAdminUser,  # noqa: ARG001
) -> QuestionDetail:
    quiz_service = QuizService(session=session)
    question = await quiz_service.create_question(quiz_id=quiz_id, data=data)
    return QuestionDetail.model_validate(question)


@router.patch("/{quiz_id}/questions/{question_id}", response_model=QuestionDetail)
async def update_question(
    quiz_id: str,
    question_id: str,
    data: QuestionUpdate,
    session: SessionDep,
    admin_user: CurrentAdminUser,  # noqa: ARG001
) -> QuestionDetail:
    quiz_service = QuizService(session=session)
    question = await quiz_service.update_question(
        quiz_id=quiz_id,
        question_id=question_id,
        data=data,
    )
    return QuestionDetail.model_validate(question)


@router.delete("/{quiz_id}/questions/{question_id}", response_model=QuestionDetail)
async def delete_question(
    quiz_id: str,
    question_id: str,
    session: SessionDep,
    admin_user: CurrentAdminUser,  # noqa: ARG001
) -> QuestionDetail:
    quiz_service = QuizService(session=session)
    question = await quiz_service.delete_question(
        quiz_id=quiz_id,
        question_id=question_id,
    )
    return QuestionDetail.model_validate(question)


@router.patch(
    "/{quiz_id}/questions/{question_id}/answers/{answer_id}",
    response_model=AnswerOptionDetail,
)
async def update_answer(
    quiz_id: str,
    question_id: str,
    answer_id: str,
    data: AnswerOptionUpdate,
    session: SessionDep,
    admin_user: CurrentAdminUser,  # noqa: ARG001
) -> AnswerOptionDetail:
    quiz_service = QuizService(session=session)
    answer = await quiz_service.update_answer(
        quiz_id=quiz_id,
        question_id=question_id,
        answer_id=answer_id,
        data=data,
    )
    return AnswerOptionDetail.model_validate(answer)


@router.delete(
    "/{quiz_id}/questions/{question_id}/answers/{answer_id}",
    response_model=AnswerOptionDetail,
)
async def delete_answer(
    quiz_id: str,
    question_id: str,
    answer_id: str,
    session: SessionDep,
    admin_user: CurrentAdminUser,  # noqa: ARG001
) -> AnswerOptionDetail:
    quiz_service = QuizService(session=session)
    answer = await quiz_service.delete_answer(
        quiz_id=quiz_id,
        question_id=question_id,
        answer_id=answer_id,
    )
    return AnswerOptionDetail.model_validate(answer)
