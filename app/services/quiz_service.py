from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from starlette import status

from app.databases.models import AnswerOption, Question, Quiz, QuizSession
from app.databases.repositories.base_repository import BaseRepository
from app.databases.repositories.quiz_repository import QuizRepository
from app.dependencies.database import SessionDep
from app.schemas.quiz import (
    AnswerOptionUpdate,
    QuestionCreate,
    QuestionType,
    QuestionUpdate,
    QuizAdminCreatedWithin,
    QuizAdminListStatus,
    QuizAdminSort,
    QuizCreate,
    QuizListResponse,
    QuizUpdate,
    SessionStatus,
)
from app.schemas.user import UserDetail
from app.utils.exceptions import DBHTTPException
from app.utils.logger import logger


class QuizService:
    _ACTIVE_SESSION_STATUSES = (
        SessionStatus.CREATED,
        SessionStatus.LOBBY,
        SessionStatus.LIVE,
        SessionStatus.PAUSED,
    )

    def __init__(self, session: SessionDep):
        self.session = session
        self.quiz_repository = QuizRepository(session=session, model=Quiz)
        self.question_repository = BaseRepository(session=session, model=Question)

    async def get_quiz(self, quiz_id: str) -> Quiz:
        stmt = (
            select(Quiz)
            .options(selectinload(Quiz.questions).selectinload(Question.answers))
            .where(Quiz.id == quiz_id)
        )
        result = await self.session.execute(stmt)
        quiz = result.scalar_one_or_none()

        if not quiz:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Quiz not found",
            )

        return quiz

    async def _get_question_with_answers(self, question_id) -> Question:
        stmt = (
            select(Question)
            .options(selectinload(Question.answers))
            .where(Question.id == question_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    @staticmethod
    def _validate_question_answers(data: QuestionCreate) -> None:
        correct_answers_count = sum(1 for answer in data.answers if answer.is_correct)

        if correct_answers_count == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one answer must be correct",
            )

        if (
            data.question_type == QuestionType.SINGLE_ANSWER
            and correct_answers_count != 1
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Single-answer question must have exactly one correct answer",
            )

    @staticmethod
    def _validate_question_answers_payload(
        question_type: QuestionType,
        answers: list[AnswerOption],
    ) -> None:
        correct_answers_count = sum(1 for answer in answers if answer.is_correct)
        QuizService._validate_correct_answers_count(
            question_type=question_type,
            correct_answers_count=correct_answers_count,
        )

    @staticmethod
    def _validate_correct_answers_count(
        question_type: QuestionType,
        correct_answers_count: int,
    ) -> None:

        if correct_answers_count == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one answer must be correct",
            )

        if (
            question_type == QuestionType.SINGLE_ANSWER
            and correct_answers_count != 1
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Single-answer question must have exactly one correct answer",
            )

    async def _get_question_or_404(self, quiz_id: str, question_id: str) -> Question:
        stmt = (
            select(Question)
            .options(selectinload(Question.answers))
            .where(Question.id == question_id, Question.quiz_id == quiz_id)
        )
        result = await self.session.execute(stmt)
        question = result.scalar_one_or_none()

        if not question:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Question not found",
            )

        return question

    async def _ensure_quiz_mutable(self, quiz_id: str) -> None:
        stmt = (
            select(QuizSession.id)
            .where(
                QuizSession.quiz_id == quiz_id,
                QuizSession.status.in_(self._ACTIVE_SESSION_STATUSES),
            )
            .limit(1)
        )
        active_session_id = await self.session.scalar(stmt)
        if active_session_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Quiz questions cannot be modified while a session is active",
            )

    async def _get_quiz_questions(self, quiz_id: str) -> list[Question]:
        stmt = (
            select(Question)
            .where(Question.quiz_id == quiz_id)
            .order_by(Question.order_index, Question.id)
        )
        result = await self.session.scalars(stmt)
        return list(result.all())

    @staticmethod
    def _validate_insert_index(order_index: int, questions_count: int) -> None:
        if order_index > questions_count:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"order_index must be between 0 and {questions_count}",
            )

    @staticmethod
    def _validate_move_index(order_index: int, questions_count: int) -> None:
        upper_bound = max(questions_count - 1, 0)
        if order_index > upper_bound:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"order_index must be between 0 and {upper_bound}",
            )

    async def _rewrite_question_order(self, questions: list[Question]) -> None:
        temporary_offset = len(questions) + 1
        for index, question in enumerate(questions, start=1):
            question.order_index = -(temporary_offset + index)
        await self.session.flush()

        for index, question in enumerate(questions):
            question.order_index = index
        await self.session.flush()

    async def _get_answer_or_404(
        self,
        quiz_id: str,
        question_id: str,
        answer_id: str,
    ) -> tuple[Question, AnswerOption]:
        question = await self._get_question_or_404(quiz_id=quiz_id, question_id=question_id)
        answer = next((item for item in question.answers if str(item.id) == answer_id), None)

        if not answer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Answer not found",
            )

        return question, answer

    async def create_quiz(self, data: QuizCreate, owner: UserDetail) -> Quiz:
        payload = data.model_dump()
        payload["owner_id"] = owner.id
        return await self.quiz_repository.create_one(payload)

    async def get_quizzes(
        self,
        page: int,
        page_size: int,
        *,
        q: str | None = None,
        status: QuizAdminListStatus | None = None,
        created: QuizAdminCreatedWithin | None = None,
        sort: QuizAdminSort | None = None,
    ) -> QuizListResponse:
        created_raw: str | None = None
        if created is not None and created != QuizAdminCreatedWithin.ALL:
            created_raw = created.value

        items, total = await self.quiz_repository.search_quizzes(
            page=page,
            page_size=page_size,
            q=q,
            status_filter=status.value if status else None,
            created_within=created_raw,
            sort=sort.value if sort else None,
        )
        return QuizListResponse(
            items=list(items),
            total=total,
            page=page,
            page_size=page_size,
        )

    async def update_quiz(self, quiz_id: str, data: QuizUpdate) -> Quiz:
        quiz = await self.quiz_repository.get_one(id=quiz_id)
        if not quiz:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Quiz not found",
            )

        update_data = data.model_dump(exclude_unset=True)
        if not update_data:
            return quiz

        updated_quiz = await self.quiz_repository.update_one(
            model_id=quiz_id,
            data=update_data,
        )
        return updated_quiz

    async def delete_quiz(self, quiz_id: str) -> Quiz:
        quiz = await self.quiz_repository.delete_one(model_id=quiz_id)
        if not quiz:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Quiz not found",
            )
        return quiz

    async def create_question(self, quiz_id: str, data: QuestionCreate) -> Question:
        await self._ensure_quiz_mutable(quiz_id)
        self._validate_question_answers(data)

        quiz = await self.quiz_repository.get_one(id=quiz_id)
        if not quiz:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Quiz not found",
            )

        questions = await self._get_quiz_questions(quiz_id)
        self._validate_insert_index(data.order_index, len(questions))

        payload = data.model_dump()
        answers_payload = payload.pop("answers")
        payload["quiz_id"] = quiz.id
        if payload["answer_time"] is None:
            payload["answer_time"] = quiz.default_question_time
        payload["order_index"] = -(len(questions) + 1)

        try:
            question = Question(**payload)
            question.answers = [AnswerOption(**answer_data) for answer_data in answers_payload]
            self.session.add(question)
            await self.session.flush()
            questions.insert(data.order_index, question)
            await self._rewrite_question_order(questions)
            await self.session.commit()
            return await self._get_question_with_answers(question.id)
        except IntegrityError as e:
            await self.session.rollback()
            logger.exception("Failed to create question for quiz_id=%s", quiz_id)

            error_message = str(e.orig)
            if "uq_question_quiz_order_index" in error_message:
                raise DBHTTPException(
                    message="Question with this order_index already exists in this quiz"
                ) from e

            raise DBHTTPException(message=f"Question create failed: {error_message}") from e

    async def update_question(
        self,
        quiz_id: str,
        question_id: str,
        data: QuestionUpdate,
    ) -> Question:
        await self._ensure_quiz_mutable(quiz_id)
        question = await self._get_question_or_404(quiz_id=quiz_id, question_id=question_id)
        update_data = data.model_dump(exclude_unset=True)
        if not update_data:
            return question

        next_question_type = update_data.get("question_type", question.question_type)
        self._validate_question_answers_payload(next_question_type, question.answers)
        next_order_index = update_data.pop("order_index", None)

        for field, value in update_data.items():
            setattr(question, field, value)

        try:
            if next_order_index is not None:
                questions = await self._get_quiz_questions(quiz_id)
                self._validate_move_index(next_order_index, len(questions))
                questions = [item for item in questions if item.id != question.id]
                questions.insert(next_order_index, question)
                await self._rewrite_question_order(questions)

            await self.session.flush()
            await self.session.commit()
        except IntegrityError as e:
            await self.session.rollback()
            logger.exception("Failed to update question question_id=%s", question_id)

            error_message = str(e.orig)
            if "uq_question_quiz_order_index" in error_message:
                raise DBHTTPException(
                    message="Question with this order_index already exists in this quiz"
                ) from e

            raise DBHTTPException(message=f"Question update failed: {error_message}") from e

        return await self._get_question_with_answers(question.id)

    async def delete_question(self, quiz_id: str, question_id: str) -> Question:
        await self._ensure_quiz_mutable(quiz_id)
        question = await self._get_question_or_404(quiz_id=quiz_id, question_id=question_id)
        questions = await self._get_quiz_questions(quiz_id)
        remaining_questions = [item for item in questions if item.id != question.id]

        await self.session.delete(question)
        await self.session.flush()
        await self._rewrite_question_order(remaining_questions)
        await self.session.commit()
        return question

    async def update_answer(
        self,
        quiz_id: str,
        question_id: str,
        answer_id: str,
        data: AnswerOptionUpdate,
    ) -> AnswerOption:
        await self._ensure_quiz_mutable(quiz_id)
        question, answer = await self._get_answer_or_404(
            quiz_id=quiz_id,
            question_id=question_id,
            answer_id=answer_id,
        )
        update_data = data.model_dump(exclude_unset=True)
        if not update_data:
            return answer

        next_is_correct = update_data.get("is_correct", answer.is_correct)
        correct_answers_count = sum(
            1
            for item in question.answers
            if (next_is_correct if item.id == answer.id else item.is_correct)
        )
        self._validate_correct_answers_count(
            question_type=question.question_type,
            correct_answers_count=correct_answers_count,
        )

        if "answer_text" in update_data:
            answer.answer_text = update_data["answer_text"]
        if "is_correct" in update_data:
            answer.is_correct = update_data["is_correct"]

        await self.session.flush()
        await self.session.commit()
        await self.session.refresh(answer)
        return answer

    async def delete_answer(
        self,
        quiz_id: str,
        question_id: str,
        answer_id: str,
    ) -> AnswerOption:
        await self._ensure_quiz_mutable(quiz_id)
        question, answer = await self._get_answer_or_404(
            quiz_id=quiz_id,
            question_id=question_id,
            answer_id=answer_id,
        )
        remaining_answers = [item for item in question.answers if item is not answer]
        self._validate_question_answers_payload(question.question_type, remaining_answers)

        await self.session.delete(answer)
        await self.session.commit()
        return answer
