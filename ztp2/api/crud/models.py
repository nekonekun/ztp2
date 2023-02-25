from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from ...db.models.ztp import Model
from ..schemas.models import ModelCreateRequest, ModelPatchRequest
from .base import CRUDBase


class ConcreteCRUD(CRUDBase[Model, ModelCreateRequest, ModelPatchRequest]):
    async def read_by_model(self, db: AsyncSession, model: str) \
            -> list[Model] | None:
        statement = select(self._schema)\
            .where(self._schema.model.contains(model))
        response = await db.execute(statement)
        target_obj = response.scalars().all()
        return target_obj


model = ConcreteCRUD(Model)
