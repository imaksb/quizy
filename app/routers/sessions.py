import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from app.dependencies.database import SessionDep
from app.dependencies.redis import RedisDep
from app.dependencies.user_validation import CurrentAdminUser
from app.schemas.quiz import (
    PlayerAnswerEvent,
    PlayerJoinEvent,
    PlayerReconnectEvent,
    SessionCreateResponse,
    SessionDetail,
)
from app.services.session_service import SessionService
from app.services.session_ws_manager import session_connection_manager

router = APIRouter(tags=["sessions"])


@router.post(
    "/quizzes/{quiz_id}/sessions",
    response_model=SessionCreateResponse,
    status_code=201,
)
async def create_session(
    quiz_id: str,
    session: SessionDep,
    redis: RedisDep,
    admin_user: CurrentAdminUser,
) -> SessionCreateResponse:
    session_service = SessionService(session=session, redis=redis)
    quiz_session = await session_service.create_session(
        quiz_id=quiz_id,
        admin_user=admin_user,
    )
    return SessionCreateResponse.model_validate(quiz_session)


@router.get("/sessions/{session_id}", response_model=SessionDetail)
async def get_session(
    session_id: str,
    session: SessionDep,
    redis: RedisDep,
    admin_user: CurrentAdminUser,
) -> SessionDetail:
    session_service = SessionService(session=session, redis=redis)
    quiz_session = await session_service.get_admin_session(
        session_id=session_id,
        admin_user=admin_user,
    )
    return SessionDetail.model_validate(quiz_session)


@router.post("/sessions/{session_id}/open", response_model=SessionDetail)
async def open_session(
    session_id: str,
    session: SessionDep,
    redis: RedisDep,
    admin_user: CurrentAdminUser,
) -> SessionDetail:
    session_service = SessionService(session=session, redis=redis)
    quiz_session = await session_service.open_session(
        session_id=session_id,
        admin_user=admin_user,
    )
    return SessionDetail.model_validate(quiz_session)


@router.post("/sessions/{session_id}/start", response_model=SessionDetail)
async def start_session(
    session_id: str,
    session: SessionDep,
    redis: RedisDep,
    admin_user: CurrentAdminUser,
) -> SessionDetail:
    session_service = SessionService(session=session, redis=redis)
    session_detail, payload = await session_service.start_session(
        session_id=session_id,
        admin_user=admin_user,
    )
    await session_connection_manager.broadcast(session_detail["id"], payload)
    return SessionDetail.model_validate(session_detail)


@router.post("/sessions/{session_id}/end", response_model=SessionDetail)
async def end_session(
    session_id: str,
    session: SessionDep,
    redis: RedisDep,
    admin_user: CurrentAdminUser,
) -> SessionDetail:
    session_service = SessionService(session=session, redis=redis)
    session_detail, payload = await session_service.end_session(
        session_id=session_id,
        admin_user=admin_user,
    )
    await session_connection_manager.broadcast(session_detail["id"], payload)
    return SessionDetail.model_validate(session_detail)


@router.websocket("/sessions/{join_code}/ws")
async def session_websocket(
    websocket: WebSocket,
    join_code: str,
    session: SessionDep,
    redis: RedisDep,
) -> None:
    await websocket.accept()
    session_service = SessionService(session=session, redis=redis)
    participant_id = None
    quiz_session_id = None

    try:
        initial_payload = await websocket.receive_json()
        quiz_session, participant, outbound_payload = await _handle_initial_payload(
            session_service=session_service,
            join_code=join_code,
            payload=initial_payload,
        )
        participant_id = participant["id"]
        quiz_session_id = quiz_session["id"]

        await session_connection_manager.connect(
            session_id=quiz_session["id"],
            participant_id=participant["id"],
            websocket=websocket,
        )
        await session_connection_manager.send_to_participant(
            session_id=quiz_session["id"],
            participant_id=participant["id"],
            payload=outbound_payload,
        )

        if outbound_payload["type"] == "participant_joined":
            public_payload = {
                **outbound_payload,
                "participant": {
                    key: value
                    for key, value in outbound_payload["participant"].items()
                    if key != "guest_token"
                },
            }
            await session_connection_manager.broadcast(
                quiz_session["id"],
                public_payload,
                exclude_participant_id=participant["id"],
            )

        while True:
            payload = await websocket.receive_json()
            event_type = payload.get("type")

            if event_type != "answer":
                await websocket.send_json(
                    {"type": "error", "detail": "Unsupported event type"}
                )
                continue

            try:
                answer_event = PlayerAnswerEvent.model_validate(payload)
                session_id, outbound_payloads, should_broadcast = (
                    await session_service.submit_answer(
                        join_code=join_code,
                        participant_id=participant["id"],
                        data=answer_event,
                    )
                )
            except (HTTPException, ValidationError) as e:
                await websocket.send_json(_error_payload(e))
                continue

            if should_broadcast:
                await _broadcast_payloads_with_leaderboard_delay(
                    session_id=session_id,
                    payloads=outbound_payloads,
                )
            else:
                await session_connection_manager.send_to_participant(
                    session_id=session_id,
                    participant_id=participant["id"],
                    payload=outbound_payloads[0],
                )

    except WebSocketDisconnect:
        if quiz_session_id and participant_id:
            await session_connection_manager.disconnect(quiz_session_id, participant_id)
            disconnected_payload = await session_service.mark_disconnected(
                quiz_session_id,
                participant_id,
            )
            if disconnected_payload:
                session_id, payloads = disconnected_payload
                await _broadcast_payloads_with_leaderboard_delay(
                    session_id=session_id,
                    payloads=payloads,
                )
    except (HTTPException, ValidationError) as e:
        await websocket.send_json(_error_payload(e))
        await websocket.close(code=1008)


async def _handle_initial_payload(
    session_service: SessionService,
    join_code: str,
    payload: dict[str, Any],
):
    event_type = payload.get("type")

    if event_type == "join":
        join_event = PlayerJoinEvent.model_validate(payload)
        return await session_service.join_lobby(
            join_code=join_code,
            player_name=join_event.player_name,
        )

    if event_type == "reconnect":
        reconnect_event = PlayerReconnectEvent.model_validate(payload)
        return await session_service.reconnect(
            join_code=join_code,
            participant_id=reconnect_event.participant_id,
            guest_token=reconnect_event.guest_token,
        )

    raise HTTPException(status_code=400, detail="First event must be join or reconnect")


def _error_payload(error: HTTPException | ValidationError) -> dict:
    if isinstance(error, ValidationError):
        return {"type": "error", "detail": error.errors()}

    return {"type": "error", "detail": error.detail}


async def _broadcast_payloads_with_leaderboard_delay(
    session_id: str,
    payloads: list[dict[str, Any]],
) -> None:
    for index, payload in enumerate(payloads):
        await session_connection_manager.broadcast(session_id, payload)
        if (
            payload.get("type") == "leaderboard_updated"
            and index < len(payloads) - 1
        ):
            await asyncio.sleep(payload.get("delay_seconds", 5))
