from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from ...db.models.ztp import User
from ..schemas.users import UserCreateRequest, UserPatchRequest
from .base import CRUDBase


class ConcreteCRUD(CRUDBase[User, UserCreateRequest, UserPatchRequest]):
    async def read_by_clauses(self, db: AsyncSession, *,
                              userside_id: int = None,
                              name: str = None,
                              telegram_id: int = None,
                              skip: int = 0, limit: int = 100) -> list[User]:
        statement = select(self._schema)
        if userside_id:
            statement = statement.where(self._schema.userside_id == userside_id)
        if telegram_id:
            statement = statement.where(self._schema.telegram_id == telegram_id)
        if name:
            statement = statement.where(self._schema.name.contains(name))
        statement = statement.order_by(desc(self._schema.id))
        statement = statement.offset(skip).limit(limit)
        response = await db.execute(statement)
        target_obj = response.scalars().all()
        return target_obj


user = ConcreteCRUD(User)
