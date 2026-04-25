import json
import secrets
import string
import uuid
from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from starlette import status

from app.databases.models import (
    Question,
    Quiz,
    QuizSession,
    SessionAnswerResult,
    SessionPlayerResult,
    SessionResult,
    SessionStatus,
)
from app.dependencies.database import SessionDep
from app.schemas.quiz import PlayerAnswerEvent, QuestionType
from app.schemas.user import UserDetail
from app.utils.exceptions import DBHTTPException
from app.utils.logger import logger


RUNTIME_TTL_SECONDS = 60 * 60 * 24
LEADERBOARD_DELAY_SECONDS = 5


class SessionService:
    def __init__(self, session: SessionDep, redis: Redis):
        self.session = session
        self.redis = redis

    @staticmethod
    def _now() -> datetime:
        return datetime.utcnow()

    @staticmethod
    def _iso_now() -> str:
        return SessionService._now().isoformat()

    @staticmethod
    def _generate_join_code() -> str:
        alphabet = string.ascii_uppercase + string.digits
        return "".join(secrets.choice(alphabet) for _ in range(6))

    @staticmethod
    def _state_key(session_id: str | UUID) -> str:
        return f"session:{session_id}:state"

    @staticmethod
    def _quiz_key(session_id: str | UUID) -> str:
        return f"session:{session_id}:quiz"

    @staticmethod
    def _participants_key(session_id: str | UUID) -> str:
        return f"session:{session_id}:participants"

    @staticmethod
    def _tokens_key(session_id: str | UUID) -> str:
        return f"session:{session_id}:tokens"

    @staticmethod
    def _scores_key(session_id: str | UUID) -> str:
        return f"session:{session_id}:scores"

    @staticmethod
    def _leaderboards_key(session_id: str | UUID) -> str:
        return f"session:{session_id}:leaderboards"

    @staticmethod
    def _answers_key(session_id: str | UUID, question_id: str) -> str:
        return f"session:{session_id}:question:{question_id}:answers"

    @staticmethod
    def _join_code_key(join_code: str) -> str:
        return f"join_code:{join_code.upper()}"

    @staticmethod
    def _runtime_keys(session_id: str | UUID, join_code: str | None) -> list[str]:
        keys = [
            SessionService._state_key(session_id),
            SessionService._quiz_key(session_id),
            SessionService._participants_key(session_id),
            SessionService._tokens_key(session_id),
            SessionService._scores_key(session_id),
            SessionService._leaderboards_key(session_id),
        ]
        if join_code:
            keys.append(SessionService._join_code_key(join_code))
        return keys

    async def _expire_runtime(self, session_id: str | UUID, join_code: str | None) -> None:
        quiz_snapshot = await self._get_quiz_snapshot(session_id)
        keys = self._runtime_keys(session_id, join_code)
        for question in quiz_snapshot["questions"]:
            keys.append(self._answers_key(session_id, question["id"]))

        pipe = self.redis.pipeline()
        for key in keys:
            pipe.expire(key, RUNTIME_TTL_SECONDS)
        await pipe.execute()

    async def _get_quiz_with_questions(self, quiz_id: str) -> Quiz:
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

    async def _get_session(
        self,
        session_id: str | UUID,
        *,
        with_quiz: bool = False,
    ) -> QuizSession:
        options = []
        if with_quiz:
            options.append(
                selectinload(QuizSession.quiz)
                .selectinload(Quiz.questions)
                .selectinload(Question.answers)
            )

        stmt = select(QuizSession).options(*options).where(QuizSession.id == session_id)
        result = await self.session.execute(stmt)
        quiz_session = result.scalar_one_or_none()

        if not quiz_session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found",
            )

        return quiz_session

    async def _get_session_by_join_code(self, join_code: str) -> QuizSession:
        session_id = await self.redis.get(self._join_code_key(join_code))
        if session_id:
            return await self._get_session(session_id, with_quiz=True)

        stmt = select(QuizSession).where(QuizSession.join_code == join_code.upper())
        result = await self.session.execute(stmt)
        quiz_session = result.scalar_one_or_none()

        if not quiz_session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found",
            )

        return quiz_session

    @staticmethod
    def _require_owner(quiz_session: QuizSession, admin_user: UserDetail) -> None:
        if quiz_session.owner_id != admin_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the session owner can perform this action",
            )

    @staticmethod
    def _quiz_snapshot(quiz: Quiz) -> dict[str, Any]:
        return {
            "id": str(quiz.id),
            "default_question_time": quiz.default_question_time,
            "questions": [
                {
                    "id": str(question.id),
                    "question_text": question.question_text,
                    "question_type": question.question_type.value,
                    "order_index": question.order_index,
                    "answer_time": question.answer_time or quiz.default_question_time,
                    "points_for_correct_answer": question.points_for_correct_answer,
                    "points_for_incorrect_answer": question.points_for_incorrect_answer,
                    "hint": question.hint,
                    "image_url": question.image_url,
                    "answers": [
                        {
                            "id": str(answer.id),
                            "answer_text": answer.answer_text,
                            "is_correct": answer.is_correct,
                        }
                        for answer in question.answers
                    ],
                }
                for question in sorted(quiz.questions, key=lambda item: item.order_index)
            ],
        }

    async def _get_quiz_snapshot(self, session_id: str | UUID) -> dict[str, Any]:
        raw_snapshot = await self.redis.get(self._quiz_key(session_id))
        if not raw_snapshot:
            quiz_session = await self._get_session(session_id, with_quiz=True)
            snapshot = self._quiz_snapshot(quiz_session.quiz)
            await self.redis.set(self._quiz_key(session_id), json.dumps(snapshot))
            return snapshot
        return json.loads(raw_snapshot)

    async def _get_state(self, session_id: str | UUID) -> dict[str, str]:
        state = await self.redis.hgetall(self._state_key(session_id))
        if not state:
            quiz_session = await self._get_session(session_id)
            state = self._db_session_state(quiz_session)
            await self.redis.hset(self._state_key(session_id), mapping=state)
            if quiz_session.join_code:
                await self.redis.set(
                    self._join_code_key(quiz_session.join_code),
                    str(quiz_session.id),
                )
        return state

    @staticmethod
    def _db_session_state(quiz_session: QuizSession) -> dict[str, str]:
        return {
            "id": str(quiz_session.id),
            "quiz_id": str(quiz_session.quiz_id),
            "owner_id": str(quiz_session.owner_id),
            "status": quiz_session.status.value,
            "join_code": quiz_session.join_code or "",
            "current_question_index": str(quiz_session.current_question_index),
            "started_at": quiz_session.started_at.isoformat()
            if quiz_session.started_at
            else "",
            "finished_at": quiz_session.finished_at.isoformat()
            if quiz_session.finished_at
            else "",
            "created_at": quiz_session.created_at.isoformat()
            if quiz_session.created_at
            else "",
            "updated_at": quiz_session.updated_at.isoformat()
            if quiz_session.updated_at
            else "",
        }

    async def _set_state_values(
        self,
        session_id: str | UUID,
        values: dict[str, str | int],
    ) -> dict[str, str]:
        await self.redis.hset(
            self._state_key(session_id),
            mapping={key: str(value) for key, value in values.items()},
        )
        return await self._get_state(session_id)

    async def _participants(self, session_id: str | UUID) -> list[dict[str, Any]]:
        raw_items = await self.redis.hgetall(self._participants_key(session_id))
        return [json.loads(value) for value in raw_items.values()]

    async def _participant(
        self,
        session_id: str | UUID,
        participant_id: str | UUID,
    ) -> dict[str, Any] | None:
        raw_item = await self.redis.hget(
            self._participants_key(session_id),
            str(participant_id),
        )
        return json.loads(raw_item) if raw_item else None

    async def _save_participant(
        self,
        session_id: str | UUID,
        participant: dict[str, Any],
    ) -> None:
        await self.redis.hset(
            self._participants_key(session_id),
            participant["id"],
            json.dumps(participant),
        )

    @staticmethod
    def _public_participant(participant: dict[str, Any]) -> dict[str, Any]:
        return {
            key: value
            for key, value in participant.items()
            if key != "guest_token"
        }

    async def _participants_payload(self, session_id: str | UUID) -> list[dict[str, Any]]:
        participants = await self._participants(session_id)
        return [
            self._public_participant(participant)
            for participant in participants
        ]

    async def _leaderboard_entries(
        self,
        session_id: str | UUID,
        *,
        question_id: str | None = None,
    ) -> list[dict[str, Any]]:
        scores = await self.redis.zrevrange(
            self._scores_key(session_id),
            0,
            -1,
            withscores=True,
        )
        participants = {
            participant["id"]: participant
            for participant in await self._participants(session_id)
        }
        last_answers: dict[str, dict[str, Any]] = {}
        if question_id:
            raw_answers = await self.redis.hgetall(self._answers_key(session_id, question_id))
            last_answers = {
                participant_id: json.loads(raw_answer)
                for participant_id, raw_answer in raw_answers.items()
            }

        entries = []
        previous_score = None
        current_rank = 0
        for index, (participant_id, score) in enumerate(scores, start=1):
            if previous_score is None or score < previous_score:
                current_rank = index
            previous_score = score
            participant = participants.get(participant_id, {})
            answer = last_answers.get(participant_id, {})
            entries.append(
                {
                    "rank": current_rank,
                    "participant_id": participant_id,
                    "guest_name": participant.get("guest_name"),
                    "status": participant.get("status"),
                    "score": int(score),
                    "last_points": answer.get("points_awarded", 0),
                    "last_answer_correct": answer.get("is_correct"),
                    "answered_at": answer.get("answered_at"),
                }
            )
        return entries

    async def get_admin_session(
        self,
        session_id: str,
        admin_user: UserDetail,
    ) -> dict[str, Any]:
        quiz_session = await self._get_session(session_id)
        self._require_owner(quiz_session, admin_user)
        state = await self._get_state(quiz_session.id)
        return await self._session_detail_payload(quiz_session, state)

    async def create_session(self, quiz_id: str, admin_user: UserDetail) -> dict[str, Any]:
        quiz = await self._get_quiz_with_questions(quiz_id)
        if not quiz.questions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Quiz must have at least one question",
            )

        for attempt in range(5):
            join_code = self._generate_join_code()
            quiz_session = QuizSession(
                quiz_id=quiz.id,
                owner_id=admin_user.id,
                status=SessionStatus.CREATED,
                join_code=join_code,
                access_link_token=secrets.token_urlsafe(32),
                current_question_index=0,
            )
            self.session.add(quiz_session)

            try:
                await self.session.flush()
                await self.session.commit()
                await self.session.refresh(quiz_session)
                snapshot = self._quiz_snapshot(quiz)
                state = self._db_session_state(quiz_session)
                await self.redis.hset(self._state_key(quiz_session.id), mapping=state)
                await self.redis.set(self._quiz_key(quiz_session.id), json.dumps(snapshot))
                await self.redis.set(self._join_code_key(join_code), str(quiz_session.id))
                return self._session_create_payload(quiz_session, state)
            except IntegrityError as e:
                await self.session.rollback()
                if attempt < 4:
                    continue

                logger.exception("Failed to create quiz session for quiz_id=%s", quiz_id)
                raise DBHTTPException(message="Quiz session create failed") from e

        raise DBHTTPException(message="Quiz session create failed")

    async def open_session(
        self,
        session_id: str,
        admin_user: UserDetail,
    ) -> dict[str, Any]:
        quiz_session = await self._get_session(session_id)
        self._require_owner(quiz_session, admin_user)
        state = await self._get_state(quiz_session.id)

        if state["status"] != SessionStatus.CREATED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only created sessions can be opened",
            )

        quiz_session.status = SessionStatus.LOBBY
        await self.session.commit()
        state = await self._set_state_values(
            quiz_session.id,
            {
                "status": SessionStatus.LOBBY.value,
                "updated_at": self._iso_now(),
            },
        )
        return await self._session_detail_payload(quiz_session, state)

    async def start_session(
        self,
        session_id: str,
        admin_user: UserDetail,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        quiz_session = await self._get_session(session_id)
        self._require_owner(quiz_session, admin_user)
        state = await self._get_state(quiz_session.id)

        if state["status"] != SessionStatus.LOBBY.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only lobby sessions can be started",
            )

        active_participants = [
            participant
            for participant in await self._participants(quiz_session.id)
            if participant["status"] != "disconnected"
        ]
        if not active_participants:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one participant is required to start session",
            )

        now = self._iso_now()
        quiz_snapshot = await self._get_quiz_snapshot(quiz_session.id)
        first_question = quiz_snapshot["questions"][0]
        quiz_session.status = SessionStatus.LIVE
        quiz_session.started_at = datetime.fromisoformat(now)
        quiz_session.current_question_index = int(first_question["order_index"])

        for participant in active_participants:
            participant["status"] = "in_progress"
            await self._save_participant(quiz_session.id, participant)

        await self.session.commit()
        state = await self._set_state_values(
            quiz_session.id,
            {
                "status": SessionStatus.LIVE.value,
                "started_at": now,
                "updated_at": now,
                "current_question_index": first_question["order_index"],
            },
        )
        payload = await self._question_opened_payload(
            quiz_session.id,
            state,
            first_question,
        )
        detail = await self._session_detail_payload(quiz_session, state)
        return detail, payload

    async def end_session(
        self,
        session_id: str,
        admin_user: UserDetail,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        quiz_session = await self._get_session(session_id)
        self._require_owner(quiz_session, admin_user)
        detail, payload = await self._finish_session(quiz_session)
        return detail, payload

    async def join_lobby(
        self,
        join_code: str,
        player_name: str,
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        quiz_session = await self._get_session_by_join_code(join_code)
        state = await self._get_state(quiz_session.id)
        if state["status"] != SessionStatus.LOBBY.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Session is not accepting participants",
            )

        participant = {
            "id": str(uuid.uuid4()),
            "guest_name": player_name,
            "guest_token": secrets.token_urlsafe(32),
            "status": "joined",
            "score": 0,
            "joined_at": self._iso_now(),
            "finished_at": None,
            "is_host": False,
        }
        await self._save_participant(quiz_session.id, participant)
        await self.redis.hset(
            self._tokens_key(quiz_session.id),
            participant["guest_token"],
            participant["id"],
        )
        await self.redis.zadd(self._scores_key(quiz_session.id), {participant["id"]: 0})

        payload = await self._participant_joined_payload(
            quiz_session.id,
            state,
            participant,
            include_token=True,
        )
        detail = await self._session_detail_payload(quiz_session, state)
        return detail, participant, payload

    async def reconnect(
        self,
        join_code: str,
        participant_id: UUID,
        guest_token: str,
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        quiz_session = await self._get_session_by_join_code(join_code)
        token_participant_id = await self.redis.hget(
            self._tokens_key(quiz_session.id),
            guest_token,
        )
        if token_participant_id != str(participant_id):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid reconnect credentials",
            )

        participant = await self._participant(quiz_session.id, participant_id)
        if not participant:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid reconnect credentials",
            )

        state = await self._get_state(quiz_session.id)
        if state["status"] == SessionStatus.FINISHED.value:
            participant["status"] = "finished"
        elif state["status"] == SessionStatus.LIVE.value:
            participant["status"] = "in_progress"
        else:
            participant["status"] = "joined"
        await self._save_participant(quiz_session.id, participant)

        payload = await self.snapshot_for_participant(quiz_session.id, participant)
        detail = await self._session_detail_payload(quiz_session, state)
        return detail, participant, payload

    async def mark_disconnected(
        self,
        session_id: str | UUID,
        participant_id: str | UUID,
    ) -> tuple[str, list[dict[str, Any]]] | None:
        participant = await self._participant(session_id, participant_id)
        if not participant or participant["status"] == "finished":
            return None

        participant["status"] = "disconnected"
        await self._save_participant(session_id, participant)
        payloads = [
            {
                "type": "participant_disconnected",
                "participant": self._public_participant(participant),
            }
        ]

        state = await self._get_state(session_id)
        if state["status"] == SessionStatus.LIVE.value:
            completion_payloads = await self._completion_payloads_if_needed(session_id)
            payloads.extend(completion_payloads)

        return str(session_id), payloads

    async def submit_answer(
        self,
        join_code: str,
        participant_id: str | UUID,
        data: PlayerAnswerEvent,
    ) -> tuple[str, list[dict[str, Any]], bool]:
        quiz_session = await self._get_session_by_join_code(join_code)
        session_id = str(quiz_session.id)
        state = await self._get_state(session_id)
        if state["status"] != SessionStatus.LIVE.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Session is not live",
            )

        participant = await self._participant(session_id, participant_id)
        if not participant or participant["status"] != "in_progress":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Participant is not active in this session",
            )

        quiz_snapshot = await self._get_quiz_snapshot(session_id)
        current_question = self._current_question(quiz_snapshot, state)
        if current_question["id"] != str(data.question_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Question is not active",
            )

        answer_key = self._answers_key(session_id, current_question["id"])
        existing_answer = await self.redis.hget(answer_key, str(participant_id))
        if existing_answer:
            return session_id, [await self._answer_accepted_payload(session_id, state)], False

        answer_payload = self._score_answer(current_question, data.answer_option_ids)
        answer_payload.update(
            {
                "participant_id": str(participant_id),
                "question_id": current_question["id"],
                "answered_at": self._iso_now(),
            }
        )
        inserted = await self.redis.hsetnx(
            answer_key,
            str(participant_id),
            json.dumps(answer_payload),
        )
        if not inserted:
            return session_id, [await self._answer_accepted_payload(session_id, state)], False

        participant["score"] += answer_payload["points_awarded"]
        await self._save_participant(session_id, participant)
        await self.redis.zincrby(
            self._scores_key(session_id),
            answer_payload["points_awarded"],
            str(participant_id),
        )

        completion_payloads = await self._completion_payloads_if_needed(session_id)
        if completion_payloads:
            return session_id, completion_payloads, True

        return session_id, [await self._answer_accepted_payload(session_id, state)], False

    async def snapshot_for_participant(
        self,
        session_id: str | UUID,
        participant: dict[str, Any],
    ) -> dict[str, Any]:
        state = await self._get_state(session_id)
        quiz_snapshot = await self._get_quiz_snapshot(session_id)
        question = None
        has_answered = False
        leaderboard = None
        if state["status"] == SessionStatus.LIVE.value:
            question = self._current_question(quiz_snapshot, state)
            has_answered = bool(
                await self.redis.hget(
                    self._answers_key(session_id, question["id"]),
                    participant["id"],
                )
            )
        raw_leaderboard = await self.redis.lindex(self._leaderboards_key(session_id), -1)
        if raw_leaderboard:
            leaderboard = json.loads(raw_leaderboard)

        return {
            "type": "snapshot",
            "session": self._session_payload(state),
            "participant": participant,
            "question": self._player_question(question) if question else None,
            "has_answered": has_answered,
            "leaderboard": leaderboard,
        }

    @staticmethod
    def _score_answer(
        question: dict[str, Any],
        answer_option_ids: list[UUID],
    ) -> dict[str, Any]:
        selected_ids = [str(answer_id) for answer_id in answer_option_ids]
        selected_set = set(selected_ids)
        if len(selected_set) != len(selected_ids):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Duplicate answer options are not allowed",
            )

        if (
            question["question_type"] == QuestionType.SINGLE_ANSWER.value
            and len(selected_set) != 1
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Single-answer question requires exactly one answer",
            )

        answer_by_id = {answer["id"]: answer for answer in question["answers"]}
        if selected_set - set(answer_by_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Answer option does not belong to active question",
            )

        correct_ids = {
            answer["id"]
            for answer in question["answers"]
            if answer["is_correct"]
        }
        is_correct = selected_set == correct_ids
        return {
            "selected_answer_option_ids": selected_ids,
            "is_correct": is_correct,
            "points_awarded": question["points_for_correct_answer"]
            if is_correct
            else question["points_for_incorrect_answer"],
        }

    async def _completion_payloads_if_needed(
        self,
        session_id: str | UUID,
    ) -> list[dict[str, Any]]:
        state = await self._get_state(session_id)
        quiz_snapshot = await self._get_quiz_snapshot(session_id)
        current_question = self._current_question(quiz_snapshot, state)
        active_participants = [
            participant
            for participant in await self._participants(session_id)
            if participant["status"] == "in_progress"
        ]
        if not active_participants:
            return []

        raw_answers = await self.redis.hgetall(
            self._answers_key(session_id, current_question["id"])
        )
        answered_participant_ids = set(raw_answers)
        active_participant_ids = {
            participant["id"]
            for participant in active_participants
        }
        if not active_participant_ids.issubset(answered_participant_ids):
            return []

        leaderboard_payload = await self._leaderboard_payload(
            session_id,
            state,
            current_question,
        )
        await self.redis.rpush(
            self._leaderboards_key(session_id),
            json.dumps(leaderboard_payload),
        )

        next_question = self._next_question(quiz_snapshot, current_question)
        if not next_question:
            quiz_session = await self._get_session(session_id)
            detail, finished_payload = await self._finish_session(quiz_session)
            return [leaderboard_payload, finished_payload]

        state = await self._set_state_values(
            session_id,
            {
                "current_question_index": next_question["order_index"],
                "updated_at": self._iso_now(),
            },
        )
        question_payload = await self._question_opened_payload(
            session_id,
            state,
            next_question,
        )
        return [leaderboard_payload, question_payload]

    async def _finish_session(
        self,
        quiz_session: QuizSession,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        session_id = str(quiz_session.id)
        finished_at = self._iso_now()
        state = await self._set_state_values(
            session_id,
            {
                "status": SessionStatus.FINISHED.value,
                "finished_at": finished_at,
                "updated_at": finished_at,
            },
        )

        for participant in await self._participants(session_id):
            if participant["status"] != "disconnected":
                participant["status"] = "finished"
                participant["finished_at"] = finished_at
                await self._save_participant(session_id, participant)

        quiz_session.status = SessionStatus.FINISHED
        quiz_session.finished_at = datetime.fromisoformat(finished_at)
        await self._persist_session_result(quiz_session, state)
        await self.session.commit()
        await self._expire_runtime(session_id, state.get("join_code"))

        detail = await self._session_detail_payload(quiz_session, state)
        return detail, await self._session_finished_payload(session_id, state)

    async def _persist_session_result(
        self,
        quiz_session: QuizSession,
        state: dict[str, str],
    ) -> None:
        existing_result = await self.session.scalar(
            select(SessionResult).where(SessionResult.session_id == quiz_session.id)
        )
        if existing_result:
            return

        session_id = str(quiz_session.id)
        participants = {
            participant["id"]: participant
            for participant in await self._participants(session_id)
        }
        leaderboard = await self._leaderboard_entries(session_id)
        result = SessionResult(
            session_id=quiz_session.id,
            quiz_id=quiz_session.quiz_id,
            owner_id=quiz_session.owner_id,
            started_at=datetime.fromisoformat(state["started_at"])
            if state.get("started_at")
            else None,
            finished_at=datetime.fromisoformat(state["finished_at"]),
            total_players=len(participants),
        )
        self.session.add(result)
        await self.session.flush()

        quiz_snapshot = await self._get_quiz_snapshot(session_id)
        questions = quiz_snapshot["questions"]
        for fallback_rank, entry in enumerate(leaderboard, start=1):
            participant = participants.get(entry["participant_id"], {})
            player_result = SessionPlayerResult(
                session_result_id=result.id,
                participant_id=UUID(entry["participant_id"]),
                guest_name=participant.get("guest_name") or "Guest",
                final_score=entry["score"],
                final_rank=entry.get("rank") or fallback_rank,
            )
            self.session.add(player_result)
            await self.session.flush()

            for question in questions:
                raw_answer = await self.redis.hget(
                    self._answers_key(session_id, question["id"]),
                    entry["participant_id"],
                )
                if not raw_answer:
                    continue
                answer = json.loads(raw_answer)
                self.session.add(
                    SessionAnswerResult(
                        player_result_id=player_result.id,
                        question_id=UUID(question["id"]),
                        selected_answer_option_ids=answer[
                            "selected_answer_option_ids"
                        ],
                        is_correct=answer["is_correct"],
                        points_awarded=answer["points_awarded"],
                        answered_at=datetime.fromisoformat(answer["answered_at"]),
                    )
                )

    @staticmethod
    def _current_question(
        quiz_snapshot: dict[str, Any],
        state: dict[str, str],
    ) -> dict[str, Any]:
        current_index = int(state["current_question_index"])
        for question in quiz_snapshot["questions"]:
            if int(question["order_index"]) == current_index:
                return question
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current question not found",
        )

    @staticmethod
    def _next_question(
        quiz_snapshot: dict[str, Any],
        current_question: dict[str, Any],
    ) -> dict[str, Any] | None:
        current_order = int(current_question["order_index"])
        return next(
            (
                question
                for question in quiz_snapshot["questions"]
                if int(question["order_index"]) > current_order
            ),
            None,
        )

    @staticmethod
    def _player_question(question: dict[str, Any]) -> dict[str, Any]:
        return {
            key: value
            for key, value in question.items()
            if key != "answers"
        } | {
            "answers": [
                {
                    "id": answer["id"],
                    "answer_text": answer["answer_text"],
                }
                for answer in question["answers"]
            ]
        }

    @staticmethod
    def _session_payload(state: dict[str, str]) -> dict[str, Any]:
        return {
            "id": state["id"],
            "quiz_id": state["quiz_id"],
            "owner_id": state.get("owner_id"),
            "status": state["status"],
            "join_code": state.get("join_code") or None,
            "current_question_index": int(state.get("current_question_index") or 0),
            "started_at": state.get("started_at") or None,
            "finished_at": state.get("finished_at") or None,
            "created_at": state.get("created_at") or None,
            "updated_at": state.get("updated_at") or None,
        }

    @staticmethod
    def _session_create_payload(
        quiz_session: QuizSession,
        state: dict[str, str],
    ) -> dict[str, Any]:
        payload = SessionService._session_payload(state)
        payload["access_link_token"] = quiz_session.access_link_token
        return payload

    async def _session_detail_payload(
        self,
        quiz_session: QuizSession,
        state: dict[str, str],
    ) -> dict[str, Any]:
        payload = self._session_create_payload(quiz_session, state)
        quiz_snapshot = await self._get_quiz_snapshot(quiz_session.id)
        payload["participants"] = await self._participants_payload(quiz_session.id)
        payload["question_states"] = [
            {
                "id": question["id"],
                "question_id": question["id"],
                "question_order_index": question["order_index"],
                "status": self._question_status(question, state),
                "started_at": state.get("started_at")
                if self._question_status(question, state) == "active"
                else None,
                "closed_at": None,
                "time_limit_seconds": question["answer_time"],
            }
            for question in quiz_snapshot["questions"]
        ]
        raw_leaderboard = await self.redis.lindex(
            self._leaderboards_key(quiz_session.id),
            -1,
        )
        payload["leaderboard"] = json.loads(raw_leaderboard) if raw_leaderboard else None
        return payload

    @staticmethod
    def _question_status(question: dict[str, Any], state: dict[str, str]) -> str:
        if state["status"] == SessionStatus.FINISHED.value:
            return "closed"
        current_index = int(state.get("current_question_index") or 0)
        order_index = int(question["order_index"])
        if state["status"] == SessionStatus.LIVE.value and order_index == current_index:
            return "active"
        if order_index < current_index:
            return "closed"
        return "pending"

    async def _participant_joined_payload(
        self,
        session_id: str | UUID,
        state: dict[str, str],
        participant: dict[str, Any],
        *,
        include_token: bool = False,
    ) -> dict[str, Any]:
        return {
            "type": "participant_joined",
            "session": self._session_payload(state),
            "participant": participant
            if include_token
            else self._public_participant(participant),
            "participants": await self._participants_payload(session_id),
        }

    async def _answer_accepted_payload(
        self,
        session_id: str | UUID,
        state: dict[str, str],
    ) -> dict[str, Any]:
        return {
            "type": "answer_accepted",
            "session": self._session_payload(state),
            "participants": await self._participants_payload(session_id),
        }

    async def _leaderboard_payload(
        self,
        session_id: str | UUID,
        state: dict[str, str],
        question: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "type": "leaderboard_updated",
            "session": self._session_payload(state),
            "question_id": question["id"],
            "question_order_index": question["order_index"],
            "delay_seconds": LEADERBOARD_DELAY_SECONDS,
            "entries": await self._leaderboard_entries(
                session_id,
                question_id=question["id"],
            ),
        }

    async def _question_opened_payload(
        self,
        session_id: str | UUID,
        state: dict[str, str],
        question: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "type": "question_opened",
            "session": self._session_payload(state),
            "question": self._player_question(question),
            "participants": await self._participants_payload(session_id),
        }

    async def _session_finished_payload(
        self,
        session_id: str | UUID,
        state: dict[str, str],
    ) -> dict[str, Any]:
        return {
            "type": "session_finished",
            "session": self._session_payload(state),
            "participants": await self._participants_payload(session_id),
            "leaderboard": await self._leaderboard_entries(session_id),
        }
