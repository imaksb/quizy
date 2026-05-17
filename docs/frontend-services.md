# Frontend Service Integration

This document describes how the frontend should work with the REST services for authentication, admin quiz management, and live session setup.

For player WebSocket gameplay, see [frontend-websockets.md](./frontend-websockets.md).

## Base Rules

Admin authentication is cookie-backed.

The backend stores JWTs in browser cookies after Google login:

- `ACCESS_TOKEN`: short-lived access JWT used for protected admin API calls.
- `REFRESH_TOKEN`: refresh JWT used only for token refresh.

Protected admin endpoints still expect the access token in the `Authorization` header:

```http
Authorization: Bearer <access_token>
```

Read the access token from the `ACCESS_TOKEN` cookie when building API requests. Do not store `access_token` or `refresh_token` in `localStorage`, `sessionStorage`, Redux, Zustand, or any other frontend persistence layer.

Only users with role `admin` can use quiz and session management endpoints.

Guest players do not log in. They join a live quiz through the WebSocket flow using `join_code` and `player_name`.

## Authentication

### Start Google Login

```http
GET /auth/
```

Current backend behavior redirects the browser to Google OAuth.

Frontend behavior:

- Navigate the admin user to `/auth/`.
- Google redirects back to the configured callback URL.
- Backend callback sets auth cookies and redirects the browser to the admin dashboard.

### Google Callback

```http
GET /auth/callback?code=<google_auth_code>
```

Response behavior:

- Sets `ACCESS_TOKEN` cookie.
- Sets `REFRESH_TOKEN` cookie.
- Redirects to `${FRONTEND_ADMIN_URL}/dashboard`.

Frontend behavior:

- Do not handle the callback response manually in frontend code.
- Let the browser follow the redirect and persist the cookies.
- Call `/users/me` after login to confirm user identity and role.

Cookie attributes:

- Development uses host-only cookies on `/`, `secure=false`, `SameSite=Lax`.
- Production uses domain cookies on `/`, `secure=true`, `SameSite=None`.
- `REFRESH_TOKEN` is `HttpOnly`; frontend code must not read it.

### Refresh Token

```http
GET /auth/refresh
```

Refresh should use the `REFRESH_TOKEN` cookie. The frontend must not copy refresh tokens into query strings, request bodies, logs, analytics, or client-side storage.

Frontend behavior:

- On `401`, try refresh once.
- Let the backend update auth cookies.
- Retry the original request once.
- If refresh fails, send the user to login.

### Current User

```http
GET /users/me
Authorization: Bearer <access_token>
```

Response:

```json
{
  "email": "admin@example.com",
  "name": "Admin",
  "picture": "https://example.com/avatar.png",
  "email_verified": true,
  "id": "48c77e70-0d82-43fe-9326-c88aef4376d0",
  "role": "admin",
  "is_ai_available": true
}
```

Frontend behavior:

- If `role !== "admin"`, block access to the admin UI.
- If `is_ai_available !== true`, hide or disable AI question generation UI.
- Show a clear "admin access required" screen.

Important: the backend creates new Google users with the default role from the database model. Admin access requires the user role to be `admin` in the database.

## Admin Quiz Flow

Recommended frontend flow:

1. Admin logs in.
2. Frontend calls `/users/me`.
3. Admin creates a quiz.
4. Admin adds questions with answer options.
5. Admin may generate questions with AI if `is_ai_available` is true.
6. Admin optionally publishes the quiz.
7. Admin creates a live session from the quiz.
8. Admin opens the session lobby.
9. Players join using `join_code`.
10. Admin starts the session.
11. Admin can end the session.

During live gameplay, runtime state is stored in Redis:

- guest participants;
- reconnect tokens;
- current question;
- answers;
- scores;
- leaderboard snapshots.

PostgreSQL stores the quiz definition, the admin-owned `QuizSession`, and final normalized results after the session ends.

## Quiz Endpoints

### Create Quiz

```http
POST /quizzes/
Authorization: Bearer <access_token>
Content-Type: application/json
```

Request:

```json
{
  "title": "General Knowledge",
  "description": "A short quiz for the team",
  "is_published": false,
  "default_question_time": 30
}
```

Response:

```json
{
  "title": "General Knowledge",
  "description": "A short quiz for the team",
  "is_published": false,
  "default_question_time": 30,
  "id": "9ab8f59d-4e8b-4303-944d-46f874ddff13",
  "owner_id": "48c77e70-0d82-43fe-9326-c88aef4376d0",
  "created_at": "2026-04-18T10:00:00",
  "updated_at": "2026-04-18T10:00:00"
}
```

Validation:

- `title`: 1-255 chars.
- `description`: 1-1000 chars.
- `default_question_time`: greater than `0`.

### List Quizzes

```http
GET /quizzes/?page=1&page_size=10
Authorization: Bearer <access_token>
```

Response:

```json
{
  "items": [
    {
      "title": "General Knowledge",
      "description": "A short quiz for the team",
      "is_published": false,
      "default_question_time": 30,
      "id": "9ab8f59d-4e8b-4303-944d-46f874ddff13",
      "owner_id": "48c77e70-0d82-43fe-9326-c88aef4376d0",
      "created_at": "2026-04-18T10:00:00",
      "updated_at": "2026-04-18T10:00:00"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 10
}
```

### Get Quiz With Questions

```http
GET /quizzes/{quiz_id}
Authorization: Bearer <access_token>
```

Response includes quiz fields and `questions`.

### Update Quiz

```http
PATCH /quizzes/{quiz_id}
Authorization: Bearer <access_token>
Content-Type: application/json
```

Request can include any subset:

```json
{
  "title": "Updated title",
  "description": "Updated description",
  "is_published": true,
  "default_question_time": 45
}
```

### Delete Quiz

```http
DELETE /quizzes/{quiz_id}
Authorization: Bearer <access_token>
```

Deletes the quiz and its related questions/sessions through database cascade rules.

## Question And Answer Endpoints

### Create Question

```http
POST /quizzes/{quiz_id}/questions
Authorization: Bearer <access_token>
Content-Type: application/json
```

Single-answer request:

```json
{
  "question_text": "What is the capital of France?",
  "question_type": "single_answer",
  "order_index": 0,
  "answer_time": 30,
  "points_for_correct_answer": 1,
  "points_for_incorrect_answer": 0,
  "hint": null,
  "image_url": null,
  "answers": [
    {
      "answer_text": "Paris",
      "is_correct": true
    },
    {
      "answer_text": "Berlin",
      "is_correct": false
    }
  ]
}
```

Multiple-answer request:

```json
{
  "question_text": "Select prime numbers",
  "question_type": "multiple_answer",
  "order_index": 1,
  "answer_time": 45,
  "points_for_correct_answer": 2,
  "points_for_incorrect_answer": 0,
  "hint": null,
  "image_url": null,
  "answers": [
    {
      "answer_text": "2",
      "is_correct": true
    },
    {
      "answer_text": "3",
      "is_correct": true
    },
    {
      "answer_text": "4",
      "is_correct": false
    }
  ]
}
```

Validation:

- `question_type` must be `single_answer` or `multiple_answer`.
- At least one answer must be correct.
- `single_answer` must have exactly one correct answer.
- `order_index` is treated as a position in the quiz.
- On create, `order_index` must be between `0` and the current question count.
- On update, `order_index` must be between `0` and the last question index.
- The backend shifts affected questions and stores sequential indexes `0..n-1`.
- If `answer_time` is `null`, backend uses `quiz.default_question_time`.
- Question and answer changes are blocked while the quiz has a session in
  `created`, `lobby`, `live`, or `paused`.

Response:

```json
{
  "question_text": "What is the capital of France?",
  "question_type": "single_answer",
  "order_index": 0,
  "answer_time": 30,
  "points_for_correct_answer": 1,
  "points_for_incorrect_answer": 0,
  "hint": null,
  "image_url": null,
  "id": "235a834e-d8cf-4320-8d8d-82d8f97e623b",
  "quiz_id": "9ab8f59d-4e8b-4303-944d-46f874ddff13",
  "created_at": "2026-04-18T10:05:00",
  "updated_at": "2026-04-18T10:05:00",
  "answers": [
    {
      "answer_text": "Paris",
      "is_correct": true,
      "id": "d93e1e62-6a49-4407-a209-710ff0ac1ea5",
      "created_at": "2026-04-18T10:05:00"
    }
  ]
}
```

### Update Question

```http
PATCH /quizzes/{quiz_id}/questions/{question_id}
Authorization: Bearer <access_token>
Content-Type: application/json
```

Request can include any subset:

```json
{
  "question_text": "Updated question",
  "question_type": "single_answer",
  "order_index": 2,
  "answer_time": 30,
  "points_for_correct_answer": 1,
  "points_for_incorrect_answer": 0,
  "hint": "Optional hint",
  "image_url": "https://example.com/image.png"
}
```

### Delete Question

```http
DELETE /quizzes/{quiz_id}/questions/{question_id}
Authorization: Bearer <access_token>
```

After deletion, the backend renumbers the remaining questions so their
`order_index` values stay sequential.

### Update Answer Option

```http
PATCH /quizzes/{quiz_id}/questions/{question_id}/answers/{answer_id}
Authorization: Bearer <access_token>
Content-Type: application/json
```

Request:

```json
{
  "answer_text": "Updated answer",
  "is_correct": true
}
```

Validation keeps question correctness valid:

- a question cannot have zero correct answers;
- a `single_answer` question cannot have more than one correct answer.

### Delete Answer Option

```http
DELETE /quizzes/{quiz_id}/questions/{question_id}/answers/{answer_id}
Authorization: Bearer <access_token>
```

Validation keeps question correctness valid after deletion.

## AI Question Generation

AI generation adds questions to an existing quiz.

Requirements:

- The request user must be authenticated.
- The request user must have `role: "admin"`.
- The request user must have `is_ai_available: true`.
- The quiz must not have a session in `created`, `lobby`, `live`, or `paused`.
- Redis must be available for per-user rate limiting.

The backend allows at most 5 AI generation attempts per user per hour.

### Generate Questions

```http
POST /ai/quizzes/{quiz_id}/questions
Authorization: Bearer <access_token>
Content-Type: application/json
```

Request:

```json
{
  "user_prompt": "Generate beginner-friendly geography questions about Europe.",
  "questions_count": 5
}
```

Validation:

- `user_prompt`: non-empty string, max 4000 characters.
- `questions_count`: integer from `1` to `10`; defaults to `5`.

Backend behavior:

- Loads the quiz title, description, default question time, and existing questions.
- Sends a strict system prompt and structured user context to the configured AI
  completions service.
- Calls `AI_COMPLETIONS_URL` with header `x-api-key: <AI_API_KEY>`.
- Validates the AI response as quiz questions before saving anything.
- Appends generated questions after existing questions.
- Assigns final sequential `order_index` values in the database.

Response:

```json
{
  "quiz_id": "9ab8f59d-4e8b-4303-944d-46f874ddff13",
  "questions": [
    {
      "question_text": "Which city is the capital of France?",
      "question_type": "single_answer",
      "order_index": 2,
      "answer_time": 30,
      "points_for_correct_answer": 1,
      "points_for_incorrect_answer": 0,
      "hint": null,
      "image_url": null,
      "id": "235a834e-d8cf-4320-8d8d-82d8f97e623b",
      "quiz_id": "9ab8f59d-4e8b-4303-944d-46f874ddff13",
      "created_at": "2026-05-17T10:05:00",
      "updated_at": "2026-05-17T10:05:00",
      "answers": [
        {
          "answer_text": "Paris",
          "is_correct": true,
          "id": "d93e1e62-6a49-4407-a209-710ff0ac1ea5",
          "created_at": "2026-05-17T10:05:00"
        },
        {
          "answer_text": "Berlin",
          "is_correct": false,
          "id": "53918332-4297-4dac-ab45-0613d9705f5a",
          "created_at": "2026-05-17T10:05:00"
        }
      ]
    }
  ]
}
```

Frontend behavior:

- Show the AI generation control only when `/users/me` returns
  `is_ai_available: true`.
- Let the admin choose or type a generation instruction and a count from 1 to 10.
- After success, merge or refetch the quiz questions using the returned saved
  questions.
- For `429`, show an hourly limit message.
- For `502`, show that AI generation failed and let the user retry later.

## Live Session Endpoints

### Create Session

```http
POST /quizzes/{quiz_id}/sessions
Authorization: Bearer <access_token>
```

Creates a session with status `created`.

Response:

```json
{
  "id": "9cf1f0d4-6b33-45cb-a88c-df6d3b4a9201",
  "quiz_id": "9ab8f59d-4e8b-4303-944d-46f874ddff13",
  "owner_id": "48c77e70-0d82-43fe-9326-c88aef4376d0",
  "status": "created",
  "join_code": "ABC123",
  "access_link_token": "token-for-linking-or-sharing",
  "current_question_index": 0,
  "started_at": null,
  "finished_at": null,
  "created_at": "2026-04-18T10:10:00",
  "updated_at": "2026-04-18T10:10:00"
}
```

Frontend behavior:

- Show the `join_code` to players.
- Do not open the player lobby screen until the admin opens the session.
- A session can be created only if the quiz has at least one question.
- Backend also seeds the Redis runtime snapshot for this session.

### Get Session

```http
GET /sessions/{session_id}
Authorization: Bearer <access_token>
```

Response:

```json
{
  "id": "9cf1f0d4-6b33-45cb-a88c-df6d3b4a9201",
  "quiz_id": "9ab8f59d-4e8b-4303-944d-46f874ddff13",
  "owner_id": "48c77e70-0d82-43fe-9326-c88aef4376d0",
  "status": "lobby",
  "join_code": "ABC123",
  "access_link_token": "token-for-linking-or-sharing",
  "current_question_index": 0,
  "started_at": null,
  "finished_at": null,
  "created_at": "2026-04-18T10:10:00",
  "updated_at": "2026-04-18T10:12:00",
  "participants": [],
  "leaderboard": null,
  "question_states": [
    {
      "id": "6a275595-76d7-4ed0-8305-cdbe5462ec31",
      "question_id": "235a834e-d8cf-4320-8d8d-82d8f97e623b",
      "question_order_index": 0,
      "status": "pending",
      "started_at": null,
      "closed_at": null,
      "time_limit_seconds": 30
    }
  ]
}
```

Only the admin who created the session can read or control it.

### Open Session Lobby

```http
POST /sessions/{session_id}/open
Authorization: Bearer <access_token>
```

Moves session from `created` to `lobby`.

Frontend behavior:

- Show `join_code` prominently.
- Allow players to connect through WebSocket.
- Show the participant list.
- Product wording may call this state `pending`; backend value is `lobby`.
- Participant list comes from Redis runtime state, not PostgreSQL participant rows.

### Start Session

```http
POST /sessions/{session_id}/start
Authorization: Bearer <access_token>
```

Moves session from `lobby` to `live`.

Frontend behavior:

- Disable new player join UI.
- Connected players receive `question_opened` through WebSocket.
- Admin UI should switch to live monitoring.
- After each question, the admin advances the session with
  `POST /sessions/{session_id}/next`.

Validation:

- Session must be in `lobby`.
- At least one active participant must be connected.

### Advance To Next Question

```http
POST /sessions/{session_id}/next
Authorization: Bearer <access_token>
```

Advances a live session from the current question to the next question.

Response: `SessionDetail`

Frontend behavior:

- Use this when the admin clicks the next-question control.
- If the current question leaderboard was not already emitted, connected players
  first receive `leaderboard_updated`.
- If another question exists, connected players receive `question_opened` after
  the leaderboard delay.
- If the current question is the last question, connected players receive
  `session_finished` after the leaderboard delay.
- Update the admin UI from the returned `SessionDetail`.

Validation:

- Session must be `live`.
- Only the session owner can advance it.

### End Session

```http
POST /sessions/{session_id}/end
Authorization: Bearer <access_token>
```

Moves session to `finished`.

Frontend behavior:

- Admin UI should show final status/results.
- Player clients receive `session_finished` through WebSocket.
- Backend persists normalized final results to PostgreSQL.
- Redis runtime state remains available for 24 hours after finish.

## Leaderboard And Final Results

The live leaderboard is Redis-backed and updated after each answered question.

Frontend player clients receive leaderboard updates through WebSocket:

```json
{
  "type": "leaderboard_updated",
  "question_id": "235a834e-d8cf-4320-8d8d-82d8f97e623b",
  "question_order_index": 0,
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

The admin can poll:

```http
GET /sessions/{session_id}
Authorization: Bearer <access_token>
```

The response includes `participants`, `question_states`, and the latest `leaderboard` snapshot when one exists.

After finish, backend creates normalized result rows:

- `SessionResult`: one row for the session summary;
- `SessionPlayerResult`: one row per player with final score and rank;
- `SessionAnswerResult`: one row per answered question per player.

There is no public result retrieval endpoint yet. If the frontend needs a dedicated results screen after page reload, add a read endpoint for these result tables.

## Error Handling

Common HTTP responses:

- `400`: invalid state transition or validation error.
- `401`: missing, invalid, or expired token.
- `403`: user is not admin, admin does not own the session, or AI generation is
  not available for the user.
- `404`: quiz, question, answer, or session not found.
- `429`: rate limit exceeded.
- `502`: upstream AI completions service failed or returned invalid output.

Recommended frontend behavior:

- For `400`, show the backend `detail` message near the form/action.
- For `401`, refresh token once and retry; if it still fails, logout.
- For `403`, show an access-denied state.
- For `404`, navigate back to a list page or show a not-found screen.

## Recommended Frontend Service Layer

Create a small API client that centralizes:

- base URL;
- reading `ACCESS_TOKEN` from cookies for Bearer token injection;
- JSON serialization;
- cookie-backed refresh retry;
- normalized error shape.

Example:

```ts
type ApiError = {
  status: number;
  detail: unknown;
};

function getCookie(name: string): string | null {
  const value = document.cookie
    .split("; ")
    .find((row) => row.startsWith(`${name}=`))
    ?.split("=")[1];

  return value ? decodeURIComponent(value) : null;
}

async function apiRequest<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const send = () => {
    const accessToken = getCookie("ACCESS_TOKEN");

    return fetch(`${API_BASE_URL}${path}`, {
      ...options,
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
        ...options.headers
      }
    });
  };

  let response = await send();

  if (response.status === 401 && path !== "/auth/refresh") {
    const refreshResponse = await fetch(`${API_BASE_URL}/auth/refresh`, {
      credentials: "include"
    });

    if (refreshResponse.ok) {
      response = await send();
    }
  }

  if (!response.ok) {
    const detail = await response.json().catch(() => null);
    throw {
      status: response.status,
      detail: detail?.detail ?? detail
    } satisfies ApiError;
  }

  return response.json() as Promise<T>;
}
```

Recommended modules:

- `authService`: login redirect, cookie-backed refresh, logout, current user.
- `quizService`: create/list/get/update/delete quiz.
- `questionService`: create/update/delete questions and answers.
- `aiService`: generate questions for an existing quiz.
- `sessionService`: create/open/start/next/end/get session.
- `gameSocketService`: player WebSocket connection and event handling.
- `leaderboardService` or UI slice: render `leaderboard_updated` and latest admin `leaderboard`.

## End-To-End Admin Example

1. Login:

```ts
window.location.href = `${API_BASE_URL}/auth/`;
```

2. Confirm admin:

```ts
const me = await apiRequest<UserDetail>("/users/me");
if (me.role !== "admin") {
  throw new Error("Admin access required");
}
```

3. Create quiz:

```ts
const quiz = await apiRequest<QuizDetail>("/quizzes/", {
  method: "POST",
  body: JSON.stringify({
    title: "General Knowledge",
    description: "A short quiz",
    is_published: false,
    default_question_time: 30
  })
});
```

4. Add question:

```ts
await apiRequest<QuestionDetail>(`/quizzes/${quiz.id}/questions`, {
  method: "POST",
  body: JSON.stringify({
    question_text: "What is the capital of France?",
    question_type: "single_answer",
    order_index: 0,
    answer_time: 30,
    points_for_correct_answer: 1,
    points_for_incorrect_answer: 0,
    hint: null,
    image_url: null,
    answers: [
      { answer_text: "Paris", is_correct: true },
      { answer_text: "Berlin", is_correct: false }
    ]
  })
});
```

5. Generate questions with AI when available:

```ts
if (me.is_ai_available) {
  await apiRequest<AIQuestionGenerationResponse>(
    `/ai/quizzes/${quiz.id}/questions`,
    {
      method: "POST",
      body: JSON.stringify({
        user_prompt: "Generate five beginner-friendly general knowledge questions",
        questions_count: 5
      })
    }
  );
}
```

6. Create and open session:

```ts
const session = await apiRequest<SessionDetail>(`/quizzes/${quiz.id}/sessions`, {
  method: "POST"
});

await apiRequest<SessionDetail>(`/sessions/${session.id}/open`, {
  method: "POST"
});
```

7. Display join code:

```ts
showJoinCode(session.join_code);
```

8. Start session after players join:

```ts
await apiRequest<SessionDetail>(`/sessions/${session.id}/start`, {
  method: "POST"
});
```

9. End session when needed:

```ts
await apiRequest<SessionDetail>(`/sessions/${session.id}/end`, {
  method: "POST"
});
```

## Implementation Notes

- Admin REST APIs and player WebSockets are separate flows.
- Do not require player registration for live sessions.
- Do not expose `is_correct` to player UI during gameplay.
- The backend currently has no dedicated admin WebSocket. Admin UI can poll `GET /sessions/{session_id}` or add an admin WebSocket later.
- `access_link_token` is returned by session creation but is not currently required by the player WebSocket endpoint.
- `is_published` exists on quizzes, but live session creation currently only requires at least one question.
- Redis is required for live sessions. If Redis is down, live-session actions will fail instead of falling back to PostgreSQL runtime writes.
- Redis is also required for AI generation rate limiting.
- AI question generation requires `AI_COMPLETIONS_URL` and `AI_API_KEY`.
