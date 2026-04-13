from __future__ import annotations

from collections.abc import Sequence
from typing import TypeVar

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")

class BaseRepository:
    def __init__(self, session: AsyncSession, model: type[T]) -> None:
        self.session = session
        self.model = model

    async def create(self, **kwargs):
        entity = self.model(**kwargs)
        self.session.add(entity)

        await self.session.commit()
        return entity

    async def get_one(self, **params) -> T:
        select_stmt = select(self.model).filter_by(**params)
        result = await self.session.execute(select_stmt)

        return result.scalar_one_or_none()

    async def update_one(self, model_id: str, data: dict) -> T:
        update_stmt = (
            update(self.model)
            .where(self.model.id == model_id)
            .values(**data)
            .returning(self.model)
        )
        result = await self.session.execute(update_stmt)
        await self.session.commit()
        return result.scalar()

    async def delete_one(self, model_id: str) -> T:
        query = (
            delete(self.model).where(self.model.id == model_id).returning(self.model)
        )
        result = await self.session.execute(query)
        await self.session.commit()
        return result.scalar()

    async def get_many(
        self, page: int = 1, page_size: int = 10, **params
    ) -> tuple[Sequence[T], int] | tuple[None, None]:
        select_stmt = (
            select(self.model)
            .filter_by(**params)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        users = await self.session.scalars(select_stmt)

        count = await self.session.execute(select(func.count(self.model.id)))
        total = count.scalar()
        return users.all(), total
