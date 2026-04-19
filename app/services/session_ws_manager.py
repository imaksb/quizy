import asyncio
from collections import defaultdict

from fastapi import WebSocket
from starlette.websockets import WebSocketState


class SessionConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[str, dict[str, WebSocket]] = defaultdict(dict)
        self._lock = asyncio.Lock()

    async def connect(
        self,
        session_id: str,
        participant_id: str,
        websocket: WebSocket,
    ) -> None:
        async with self._lock:
            previous_websocket = self._connections[session_id].get(participant_id)
            if (
                previous_websocket
                and previous_websocket.client_state == WebSocketState.CONNECTED
            ):
                await previous_websocket.close(code=4000, reason="Reconnected elsewhere")
            self._connections[session_id][participant_id] = websocket

    async def disconnect(self, session_id: str, participant_id: str) -> None:
        async with self._lock:
            session_connections = self._connections.get(session_id)
            if not session_connections:
                return

            session_connections.pop(participant_id, None)
            if not session_connections:
                self._connections.pop(session_id, None)

    async def send_to_participant(
        self,
        session_id: str,
        participant_id: str,
        payload: dict,
    ) -> None:
        websocket = self._connections.get(session_id, {}).get(participant_id)
        if websocket and websocket.client_state == WebSocketState.CONNECTED:
            await websocket.send_json(payload)

    async def broadcast(
        self,
        session_id: str,
        payload: dict,
        *,
        exclude_participant_id: str | None = None,
    ) -> None:
        connections = list(self._connections.get(session_id, {}).items())
        disconnected: list[str] = []

        for participant_id, websocket in connections:
            if participant_id == exclude_participant_id:
                continue

            if websocket.client_state != WebSocketState.CONNECTED:
                disconnected.append(participant_id)
                continue

            try:
                await websocket.send_json(payload)
            except RuntimeError:
                disconnected.append(participant_id)

        if disconnected:
            async with self._lock:
                session_connections = self._connections.get(session_id, {})
                for participant_id in disconnected:
                    session_connections.pop(participant_id, None)


session_connection_manager = SessionConnectionManager()
