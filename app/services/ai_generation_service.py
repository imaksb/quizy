import json
import time
from typing import Any

import httpx
from fastapi import HTTPException
from redis.asyncio import Redis
from starlette import status

from app.core.settings import settings
from app.databases.models import AnswerOption, Question, Quiz
from app.dependencies.database import SessionDep
from app.schemas.ai import AIGeneratedQuestions, AIQuestionGenerationRequest
from app.schemas.quiz import QuestionCreate
from app.schemas.user import UserDetail
from app.services.quiz_service import QuizService

AI_SYSTEM_PROMPT = """
You generate quiz questions for the Quizy application.

Return only a raw JSON object. Do not wrap it in markdown. Do not include
comments, explanations, code fences, or extra fields.

The JSON object must have exactly this top-level shape:
{
  "questions": [
    {
      "question_text": "Question text",
      "question_type": "single_answer",
      "order_index": 0,
      "answer_time": 30,
      "points_for_correct_answer": 1,
      "points_for_incorrect_answer": 0,
      "hint": null,
      "image_url": null,
      "answers": [
        {"answer_text": "Answer A", "is_correct": true},
        {"answer_text": "Answer B", "is_correct": false}
      ]
    }
  ]
}

Rules:
- Generate no more questions than requested.
- question_type must be either "single_answer" or "multiple_answer".
- single_answer questions must have exactly one correct answer.
- multiple_answer questions must have at least one correct answer.
- Each question must have at least two answer options and at most six.
- Make incorrect answers plausible.
- Avoid duplicating existing questions.
- Use the language of the user's request; if unclear, use the quiz title and
  description language.
- Set image_url to null.
- Set order_index to 0 for every generated question. The backend will assign
  final order indexes.
""".strip()


class AIQuestionGenerationService:
    RATE_LIMIT = 5
    RATE_LIMIT_SECONDS = 60 * 60

    def __init__(self, session: SessionDep, redis: Redis):
        self.session = session
        self.redis = redis
        self.quiz_service = QuizService(session=session)

    async def generate_questions(
        self,
        quiz_id: str,
        data: AIQuestionGenerationRequest,
        user: UserDetail,
    ) -> list[Question]:
        if not user.is_ai_available:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="AI question generation is not available for this user",
            )

        await self._consume_rate_limit(user.id)
        await self.quiz_service._ensure_quiz_mutable(quiz_id)
        quiz = await self._get_quiz_or_404(quiz_id)

        ai_payload = await self._request_completion(
            system_prompt=AI_SYSTEM_PROMPT,
            user_input=self._build_user_prompt(quiz, data),
        )
        generated_questions = self._parse_questions(
            output=ai_payload,
            requested_count=data.questions_count,
        )
        return await self._append_questions(quiz, generated_questions)

    async def _consume_rate_limit(self, user_id: Any) -> None:
        hour_bucket = int(time.time() // self.RATE_LIMIT_SECONDS)
        key = f"ai:question_generation:{user_id}:{hour_bucket}"
        attempts = await self.redis.incr(key)
        if attempts == 1:
            await self.redis.expire(key, self.RATE_LIMIT_SECONDS)

        if attempts > self.RATE_LIMIT:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="AI question generation rate limit exceeded",
            )

    async def _get_quiz_or_404(self, quiz_id: str) -> Quiz:
        quiz = await self.quiz_service.get_quiz(quiz_id=quiz_id)
        return quiz

    @staticmethod
    def _build_user_prompt(quiz: Quiz, data: AIQuestionGenerationRequest) -> str:
        existing_questions = [
            {
                "question_text": question.question_text,
                "question_type": question.question_type.value,
                "answers": [
                    {
                        "answer_text": answer.answer_text,
                        "is_correct": answer.is_correct,
                    }
                    for answer in question.answers
                ],
            }
            for question in sorted(quiz.questions, key=lambda item: item.order_index)
        ]
        context = {
            "requested_questions_count": data.questions_count,
            "user_prompt": data.user_prompt,
            "quiz": {
                "title": quiz.title,
                "description": quiz.description,
                "default_question_time": quiz.default_question_time,
            },
            "existing_questions": existing_questions,
        }
        return json.dumps(context, ensure_ascii=False)

    async def _request_completion(self, system_prompt: str, user_input: str) -> str:
        if not settings.AI_COMPLETIONS_URL or not settings.AI_API_KEY:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="AI completions service is not configured",
            )

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(
                    settings.AI_COMPLETIONS_URL,
                    json={
                        "system_prompt": system_prompt,
                        "user_input": user_input,
                    },
                    headers={"x-api-key": settings.AI_API_KEY},
                )
        except httpx.HTTPError as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="AI completions service request failed",
            ) from e

        if response.status_code != status.HTTP_200_OK:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="AI completions service returned an error",
            )

        try:
            payload = response.json()
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Invalid AI completion response",
            ) from e

        output = payload.get("output")
        if not isinstance(output, str) or not output.strip():
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Invalid AI completion response",
            )
        return output

    @staticmethod
    def _parse_questions(output: str, requested_count: int) -> list[QuestionCreate]:
        try:
            raw_payload = json.loads(output)
            parsed = AIGeneratedQuestions.model_validate(raw_payload)
        except (ValueError, TypeError) as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Invalid AI completion response",
            ) from e

        if len(parsed.questions) > requested_count:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Invalid AI completion response",
            )

        for question in parsed.questions:
            if len(question.answers) < 2 or len(question.answers) > 6:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Invalid AI completion response",
                )
            QuizService._validate_question_answers(question)

        return parsed.questions

    async def _append_questions(
        self,
        quiz: Quiz,
        questions: list[QuestionCreate],
    ) -> list[Question]:
        existing_questions = await self.quiz_service._get_quiz_questions(str(quiz.id))
        next_order_index = len(existing_questions)
        created_questions: list[Question] = []

        for index, question_data in enumerate(questions):
            payload = question_data.model_dump()
            answers_payload = payload.pop("answers")
            payload["quiz_id"] = quiz.id
            payload["order_index"] = next_order_index + index
            if payload["answer_time"] is None:
                payload["answer_time"] = quiz.default_question_time

            question = Question(**payload)
            question.answers = [
                AnswerOption(**answer_data) for answer_data in answers_payload
            ]
            self.session.add(question)
            created_questions.append(question)

        await self.session.flush()
        question_ids = [question.id for question in created_questions]
        await self.session.commit()
        return [
            await self.quiz_service._get_question_with_answers(question_id)
            for question_id in question_ids
        ]
