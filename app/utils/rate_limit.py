from __future__ import annotations

import time
from collections import defaultdict, deque
from collections.abc import Callable

from fastapi import HTTPException, Request
from starlette import status

from app.core.settings import settings

_buckets: dict[str, deque[float]] = defaultdict(deque)


def _client_key(request: Request, scope: str) -> str:
    forwarded_for = request.headers.get("x-forwarded-for", "")
    client_ip = forwarded_for.split(",", 1)[0].strip()
    if not client_ip and request.client:
        client_ip = request.client.host
    return f"{scope}:{client_ip or 'unknown'}"


def rate_limit(scope: str, *, limit: int | None = None) -> Callable[[Request], None]:
    def dependency(request: Request) -> None:
        if not settings.RATE_LIMIT_ENABLED:
            return

        max_requests = limit or settings.RATE_LIMIT_REQUESTS
        window_seconds = settings.RATE_LIMIT_WINDOW_SECONDS
        now = time.monotonic()
        bucket = _buckets[_client_key(request, scope)]

        while bucket and now - bucket[0] >= window_seconds:
            bucket.popleft()

        if len(bucket) >= max_requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests",
            )

        bucket.append(now)

    return dependency
