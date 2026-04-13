from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from starlette import status

from app.databases.models import AnswerOption, Question, Quiz
from app.databases.repositories.base_repository import BaseRepository
from app.databases.repositories.quiz_repository import QuizRepository
from app.dependencies.database import SessionDep
from app.schemas.quiz import (
    AnswerOptionUpdate,
    QuestionCreate,
    QuestionUpdate,
    QuestionType,
    QuizCreate,
    QuizListResponse,
    QuizUpdate,
)
from app.schemas.user import UserDetail
from app.utils.exceptions import DBHTTPException
from app.utils.logger import logger


class QuizService:
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

    async def get_quizzes(self, page: int, page_size: int) -> QuizListResponse:
        items, total = await self.quiz_repository.get_many(
            page=page,
            page_size=page_size,
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
        self._validate_question_answers(data)

        quiz = await self.quiz_repository.get_one(id=quiz_id)
        if not quiz:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Quiz not found",
            )

        payload = data.model_dump()
        answers_payload = payload.pop("answers")
        payload["quiz_id"] = quiz.id
        if payload["answer_time"] is None:
            payload["answer_time"] = quiz.default_question_time

        try:
            question = Question(**payload)
            question.answers = [AnswerOption(**answer_data) for answer_data in answers_payload]
            self.session.add(question)
            await self.session.flush()
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
        question = await self._get_question_or_404(quiz_id=quiz_id, question_id=question_id)
        update_data = data.model_dump(exclude_unset=True)
        if not update_data:
            return question

        next_question_type = update_data.get("question_type", question.question_type)
        self._validate_question_answers_payload(next_question_type, question.answers)

        for field, value in update_data.items():
            setattr(question, field, value)

        try:
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
        question = await self._get_question_or_404(quiz_id=quiz_id, question_id=question_id)

        await self.session.delete(question)
        await self.session.commit()
        return question

    async def update_answer(
        self,
        quiz_id: str,
        question_id: str,
        answer_id: str,
        data: AnswerOptionUpdate,
    ) -> AnswerOption:
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
