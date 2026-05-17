# Quizy API

FastAPI backend for Quizy. The HTTP API is documented with OpenAPI/Swagger.
WebSocket API documentation is maintained separately with AsyncAPI because
FastAPI does not include WebSocket routes in the OpenAPI schema.

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
