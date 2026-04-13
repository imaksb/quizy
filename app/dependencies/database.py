from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.databases.postgres import SessionPool


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionPool() as session:
        yield session

SessionDep = Annotated[AsyncSession, Depends(get_session)]
