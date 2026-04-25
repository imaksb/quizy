# Frontend WebSocket Integration

This document describes how the frontend should work with live quiz sessions over WebSockets.
In the local backend work in localhost:8001/
## Session Lifecycle

Admin controls the session through REST endpoints:

1. `POST /quizzes/{quiz_id}/sessions`
   - Creates a session with status `created`.
   - Response includes `id`, `join_code`, and `access_link_token`.

2. `POST /sessions/{session_id}/open`
   - Moves the session to `lobby`.
   - Players can connect only while the session is in `lobby`.
   - Product wording may call this state `pending`; backend value is `lobby`.

3. `POST /sessions/{session_id}/start`
   - Moves the session to `live`.
   - Registration is closed.
   - Connected players receive the first question through WebSocket.
   - Runtime player state, answers, scores, and leaderboard are stored in Redis.

4. `POST /sessions/{session_id}/end`
   - Moves the session to `finished`.
   - Connected players receive the final session state.
   - Final normalized session results are saved to PostgreSQL.
   - Redis runtime state remains available for reconnect/result viewing for 24 hours.

Player gameplay happens through:

```text
WS /sessions/{join_code}/ws
```

Example:

```text
wss://api.example.com/sessions/ABC123/ws
```

Use `ws://` in local development and `wss://` in production.

## First WebSocket Message

After opening the WebSocket, the first message must identify the player. It must be either `join` or `reconnect`.

### New Player Join

Use this when the player has no saved session credentials.

```json
{
  "type": "join",
  "player_name": "Anna"
}
```

The server responds privately to that player:

```json
{
  "type": "participant_joined",
  "session": {
    "id": "9cf1f0d4-6b33-45cb-a88c-df6d3b4a9201",
    "quiz_id": "9ab8f59d-4e8b-4303-944d-46f874ddff13",
    "status": "lobby",
    "join_code": "ABC123",
    "current_question_index": 0,
    "started_at": null,
    "finished_at": null
  },
  "participant": {
    "id": "c28f8841-98f6-4570-9e51-897f917fb3e4",
    "guest_name": "Anna",
    "status": "joined",
    "score": 0,
    "is_host": false,
    "guest_token": "secret-token-from-server"
  },
  "participants": [
    {
      "id": "c28f8841-98f6-4570-9e51-897f917fb3e4",
      "guest_name": "Anna",
      "status": "joined",
      "score": 0,
      "is_host": false
    }
  ]
}
```

The frontend must persist these values locally:

```json
{
  "join_code": "ABC123",
  "participant_id": "c28f8841-98f6-4570-9e51-897f917fb3e4",
  "guest_token": "secret-token-from-server",
  "player_name": "Anna"
}
```

Recommended storage:

- Use `sessionStorage` if reconnect only needs to survive page refreshes in the same browser tab.
- Use `localStorage` if reconnect should survive browser restarts.
- Treat `guest_token` as a secret. Do not show it in UI, URLs, logs, analytics, or error reports.

### Reconnect

Use this when saved `participant_id` and `guest_token` exist for the current `join_code`.

```json
{
  "type": "reconnect",
  "participant_id": "c28f8841-98f6-4570-9e51-897f917fb3e4",
  "guest_token": "secret-token-from-server"
}
```

The server responds with a snapshot:

```json
{
  "type": "snapshot",
  "session": {
    "id": "9cf1f0d4-6b33-45cb-a88c-df6d3b4a9201",
    "quiz_id": "9ab8f59d-4e8b-4303-944d-46f874ddff13",
    "status": "live",
    "join_code": "ABC123",
    "current_question_index": 1,
    "started_at": "2026-04-18T10:30:00",
    "finished_at": null
  },
  "participant": {
    "id": "c28f8841-98f6-4570-9e51-897f917fb3e4",
    "guest_name": "Anna",
    "status": "in_progress",
    "score": 1,
    "is_host": false,
    "guest_token": "secret-token-from-server"
  },
  "question": {
    "id": "235a834e-d8cf-4320-8d8d-82d8f97e623b",
    "question_text": "Which answer is correct?",
    "question_type": "single_answer",
    "order_index": 1,
    "answer_time": 30,
    "points_for_correct_answer": 1,
    "points_for_incorrect_answer": 0,
    "hint": null,
    "image_url": null,
    "answers": [
      {
        "id": "d93e1e62-6a49-4407-a209-710ff0ac1ea5",
        "answer_text": "Answer A"
      },
      {
        "id": "53918332-4297-4dac-ab45-0613d9705f5a",
        "answer_text": "Answer B"
      }
    ]
  },
  "has_answered": false
}
```

If `has_answered` is `true`, disable answer controls and show the waiting state.

## Client Events

After the first `join` or `reconnect` message, the frontend may send answer events.

### Submit Answer

```json
{
  "type": "answer",
  "question_id": "235a834e-d8cf-4320-8d8d-82d8f97e623b",
  "answer_option_ids": [
    "d93e1e62-6a49-4407-a209-710ff0ac1ea5"
  ]
}
```

For `single_answer`, send exactly one `answer_option_id`.

For `multiple_answer`, send one or more `answer_option_ids`.

Do not send answer text. Always send answer option ids from the current `question.answers`.

## Server Events

The frontend must handle these event types.

### `participant_joined`

Sent when a player joins the lobby.

Use it to update the lobby participant list.

The joining player receives a private version with `participant.guest_token`. Other players receive the same event without `guest_token`.

### `participant_disconnected`

Sent when a player disconnects.

```json
{
  "type": "participant_disconnected",
  "participant": {
    "id": "c28f8841-98f6-4570-9e51-897f917fb3e4",
    "guest_name": "Anna",
    "status": "disconnected",
    "score": 0,
    "is_host": false
  }
}
```

Use it to show a disconnected state in the lobby or scoreboard.

Disconnected players do not block question progression.

### `leaderboard_updated`

Sent after all active players answer the current question.

The frontend should show this screen before the next question. The backend waits `delay_seconds` before broadcasting `question_opened` or `session_finished`.

```json
{
  "type": "leaderboard_updated",
  "session": {
    "id": "9cf1f0d4-6b33-45cb-a88c-df6d3b4a9201",
    "quiz_id": "9ab8f59d-4e8b-4303-944d-46f874ddff13",
    "status": "live",
    "join_code": "ABC123",
    "current_question_index": 1,
    "started_at": "2026-04-18T10:30:00",
    "finished_at": null
  },
  "question_id": "235a834e-d8cf-4320-8d8d-82d8f97e623b",
  "question_order_index": 1,
  "delay_seconds": 5,
  "entries": [
    {
      "rank": 1,
      "participant_id": "c28f8841-98f6-4570-9e51-897f917fb3e4",
      "guest_name": "Anna",
      "status": "in_progress",
      "score": 3,
      "last_points": 1,
      "last_answer_correct": true,
      "answered_at": "2026-04-18T10:31:05"
    }
  ]
}
```

Frontend behavior:

- Move from question/waiting screen to leaderboard screen.
- Highlight the current player by matching `participant_id`.
- Show `rank`, `guest_name`, `score`, and current player result for the previous question.
- Keep answer controls disabled.
- Wait for the next server event. Do not locally open the next question.

### `question_opened`

Sent when the session starts or advances to the next question.

```json
{
  "type": "question_opened",
  "session": {
    "id": "9cf1f0d4-6b33-45cb-a88c-df6d3b4a9201",
    "quiz_id": "9ab8f59d-4e8b-4303-944d-46f874ddff13",
    "status": "live",
    "join_code": "ABC123",
    "current_question_index": 1,
    "started_at": "2026-04-18T10:30:00",
    "finished_at": null
  },
  "question": {
    "id": "235a834e-d8cf-4320-8d8d-82d8f97e623b",
    "question_text": "Which answer is correct?",
    "question_type": "single_answer",
    "order_index": 1,
    "answer_time": 30,
    "points_for_correct_answer": 1,
    "points_for_incorrect_answer": 0,
    "hint": null,
    "image_url": null,
    "answers": [
      {
        "id": "d93e1e62-6a49-4407-a209-710ff0ac1ea5",
        "answer_text": "Answer A"
      }
    ]
  },
  "participants": []
}
```

Frontend behavior:

- Move from lobby/waiting screen to question screen.
- Render answer controls based on `question.question_type`.
- Clear any previous selected answers.
- Enable answer submission.
- Start a local countdown using `question.answer_time` if present.

The current backend does not auto-submit when the local timer reaches zero. The frontend may disable controls locally at zero, but server-side timeout enforcement is not implemented yet.

### `answer_accepted`

Sent privately to the player whose answer was accepted.

```json
{
  "type": "answer_accepted",
  "session": {
    "id": "9cf1f0d4-6b33-45cb-a88c-df6d3b4a9201",
    "quiz_id": "9ab8f59d-4e8b-4303-944d-46f874ddff13",
    "status": "live",
    "join_code": "ABC123",
    "current_question_index": 1,
    "started_at": "2026-04-18T10:30:00",
    "finished_at": null
  },
  "participants": []
}
```

Frontend behavior:

- Disable answer controls.
- Show a waiting state.
- Do not navigate to the next question until `question_opened` arrives.

If all active players have answered, the server may skip `answer_accepted` and broadcast `leaderboard_updated` instead.

### `session_finished`

Sent when the quiz ends.

```json
{
  "type": "session_finished",
  "session": {
    "id": "9cf1f0d4-6b33-45cb-a88c-df6d3b4a9201",
    "quiz_id": "9ab8f59d-4e8b-4303-944d-46f874ddff13",
    "status": "finished",
    "join_code": "ABC123",
    "current_question_index": 2,
    "started_at": "2026-04-18T10:30:00",
    "finished_at": "2026-04-18T10:35:00"
  },
  "participants": [
    {
      "id": "c28f8841-98f6-4570-9e51-897f917fb3e4",
      "guest_name": "Anna",
      "status": "finished",
      "score": 3,
      "is_host": false
    }
  ],
  "leaderboard": [
    {
      "rank": 1,
      "participant_id": "c28f8841-98f6-4570-9e51-897f917fb3e4",
      "guest_name": "Anna",
      "status": "finished",
      "score": 3,
      "last_points": 1,
      "last_answer_correct": true,
      "answered_at": "2026-04-18T10:34:40"
    }
  ]
}
```

Frontend behavior:

- Stop timers.
- Disable answer controls.
- Show final score/results screen.
- Keep saved reconnect credentials until the user leaves the session intentionally.

### `error`

Sent when the server rejects a client event.

```json
{
  "type": "error",
  "detail": "Session is not accepting participants"
}
```

Frontend behavior:

- Show a user-friendly error.
- Keep the socket open unless the backend closes it.
- If the socket closes with an auth or validation error, clear invalid reconnect credentials and let the user join again if the session is still in lobby.

## Recommended Frontend State Machine

Use explicit states instead of deriving UI only from socket status.

```text
idle
  -> connecting
  -> lobby
  -> question
  -> waiting_for_players
  -> leaderboard
  -> finished
  -> connection_lost
  -> error
```

Suggested transitions:

- `connecting -> lobby`
  - after `participant_joined` or `snapshot` with `session.status = "lobby"`.

- `lobby -> question`
  - after `question_opened`.

- `question -> waiting_for_players`
  - after sending an answer and receiving `answer_accepted`.

- `question | waiting_for_players -> leaderboard`
  - after `leaderboard_updated`.

- `leaderboard -> question`
  - after next `question_opened`.

- `leaderboard -> finished`
  - after `session_finished`.

- `question | waiting_for_players | lobby -> connection_lost`
  - when the WebSocket closes unexpectedly.

- `connection_lost -> connecting`
  - when retrying with `reconnect`.

- any state -> `finished`
  - after `session_finished` or `snapshot` with `session.status = "finished"`.

## Reconnect Strategy

Recommended behavior:

1. On successful `join`, save `join_code`, `participant_id`, and `guest_token`.
2. On page reload, if all three values exist, connect to `/sessions/{join_code}/ws`.
3. Send `reconnect` as the first message.
4. Render UI from the returned `snapshot`.
5. If reconnect fails, clear saved credentials for that join code.
6. If the session is still in lobby, allow the user to join again.

Use exponential retry for temporary network failures:

```text
1s -> 2s -> 5s -> 10s
```

Stop retrying when:

- the user leaves the page;
- the server returns a validation/auth error;
- the session is finished.

## Minimal Browser Example

```ts
type SavedParticipant = {
  join_code: string;
  participant_id: string;
  guest_token: string;
  player_name: string;
};

function connectToSession(joinCode: string, playerName: string) {
  const savedRaw = localStorage.getItem(`quiz-session:${joinCode}`);
  const saved = savedRaw ? (JSON.parse(savedRaw) as SavedParticipant) : null;

  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  const socket = new WebSocket(`${protocol}://api.example.com/sessions/${joinCode}/ws`);

  socket.addEventListener("open", () => {
    if (saved?.participant_id && saved?.guest_token) {
      socket.send(JSON.stringify({
        type: "reconnect",
        participant_id: saved.participant_id,
        guest_token: saved.guest_token
      }));
      return;
    }

    socket.send(JSON.stringify({
      type: "join",
      player_name: playerName
    }));
  });

  socket.addEventListener("message", (event) => {
    const message = JSON.parse(event.data);

    switch (message.type) {
      case "participant_joined":
        if (message.participant.guest_token) {
          localStorage.setItem(`quiz-session:${joinCode}`, JSON.stringify({
            join_code: joinCode,
            participant_id: message.participant.id,
            guest_token: message.participant.guest_token,
            player_name: message.participant.guest_name
          }));
        }
        renderLobby(message.participants);
        break;

      case "snapshot":
        renderFromSnapshot(message);
        break;

      case "question_opened":
        renderQuestion(message.question);
        break;

      case "answer_accepted":
        renderWaiting();
        break;

      case "leaderboard_updated":
        renderLeaderboard(message.entries);
        break;

      case "participant_disconnected":
        markParticipantDisconnected(message.participant);
        break;

      case "session_finished":
        renderResults(message.participants);
        break;

      case "error":
        showError(message.detail);
        break;
    }
  });

  return socket;
}

function submitAnswer(socket: WebSocket, questionId: string, answerOptionIds: string[]) {
  socket.send(JSON.stringify({
    type: "answer",
    question_id: questionId,
    answer_option_ids: answerOptionIds
  }));
}
```

Replace `api.example.com` with the real API host.

## Important Notes

- The frontend must never display correct answers during the live quiz. The WebSocket question payload intentionally does not include `is_correct`.
- The frontend should not allow changing an answer after submission.
- The frontend should wait for server events instead of locally advancing questions.
- After each question, the frontend should expect `leaderboard_updated` before the next `question_opened`.
- Joining after session start is not allowed.
- Reconnect is allowed after session start only with valid saved credentials.
- Runtime game state is stored in Redis and expires 24 hours after finish.
- Current WebSocket connection registry is still in-memory. If the backend is deployed with multiple workers or instances, connection broadcasts require Redis pub/sub or another shared channel.
