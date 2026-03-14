"""Base Repository — Generic CRUD with hook integration (Repository Pattern)."""
from __future__ import annotations
from typing import TypeVar, Generic, Type
from sqlalchemy import select, func, delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase
from backend.app.core.hooks import hooks

T = TypeVar("T", bound=DeclarativeBase)

class BaseRepository(Generic[T]):
    model: Type[T]

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, entity_id: int) -> T | None:
        return await self._session.get(self.model, entity_id)

    async def get_all(self, offset: int = 0, limit: int = 20, order_by: str | None = None) -> list[T]:
        stmt = select(self.model)
        if order_by:
            col = getattr(self.model, order_by.lstrip("-"), None)
            if col is not None:
                stmt = stmt.order_by(col.desc() if order_by.startswith("-") else col.asc())
        stmt = stmt.offset(offset).limit(limit)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count(self) -> int:
        stmt = select(func.count()).select_from(self.model)
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def create(self, entity: T, hook_name: str | None = None) -> T:
        self._session.add(entity)
        await self._session.flush()
        if hook_name:
            await hooks.do_action(hook_name, entity=entity)
        return entity

    async def update(self, entity: T, hook_name: str | None = None) -> T:
        merged = await self._session.merge(entity)
        await self._session.flush()
        if hook_name:
            await hooks.do_action(hook_name, entity=merged)
        return merged

    async def delete(self, entity_id: int, hook_name: str | None = None) -> bool:
        entity = await self.get_by_id(entity_id)
        if entity is None:
            return False
        if hook_name:
            await hooks.do_action(hook_name, entity=entity)
        await self._session.delete(entity)
        await self._session.flush()
        return True

    def _base_query(self):
        return select(self.model)
