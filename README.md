# Quizy API

FastAPI backend for Quizy. The HTTP API is documented with OpenAPI/Swagger.
WebSocket API documentation is maintained separately with AsyncAPI because
FastAPI does not include WebSocket routes in the OpenAPI schema.

## Local Setup

Create an environment file from the example and fill real secrets:

```text
cp .env.example .env
```

Run the development stack:

```text
docker compose -f docker-compose-dev.yml up --build
```

Apply migrations when the database is available:

```text
uv run alembic upgrade head
```

Run checks:

```text
uv run ruff check app tests
uv run black --check app tests
uv run mypy
uv run pytest
```

## Production Notes

- Use `ENVIRONMENT=production`.
- Set strong values for `AUTH_SECRET_KEY`, `OPENAPI_SWAGGER_PASSWORD`,
  `POSTGRES_PASSWORD`, and Google OAuth secrets.
- Keep `CORS_ALLOWED_ORIGIN_REGEX` empty in production unless a reviewed
  domain regex is required. Localhost CORS regex is only enabled by default
  in development.
- `/auth/refresh` reads the `REFRESH_TOKEN` HttpOnly cookie and rotates both
  auth cookies. Do not send refresh tokens in URLs.
- `GET /health` is available for container and proxy health checks.
- Quiz image uploads accept WebP only and are served from
  `QUIZ_UPLOAD_URL_PREFIX`.
- Run Alembic migrations before starting new application versions.

## WebSocket AsyncAPI

Spec file:

```text
docs/asyncapi.yaml
```

Local viewer:

```text
GET /docs/ws
```

Raw spec:

```text
GET /asyncapi.yaml
```

Both routes use the same Basic Auth credentials as `/docs`, `/redoc`, and
`/openapi.json`.

Documented WebSocket endpoint:

```text
WS /sessions/{join_code}/ws
```

The endpoint accepts no query parameters. The client must send `join` or
`reconnect` as the first JSON message. After that, clients may send `answer`
messages, and the server may emit `participant_joined`, `snapshot`,
`question_opened`, `answer_accepted`, `leaderboard_updated`,
`participant_disconnected`, `session_finished`, and `error`.
