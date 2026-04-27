from typing import Annotated

from fastapi import Depends
from redis.asyncio import Redis

from app.databases.redis_server import RedisPool


async def get_redis() -> Redis:
    return RedisPool


RedisDep = Annotated[Redis, Depends(get_redis)]
