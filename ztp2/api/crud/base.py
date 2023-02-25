from typing import Any, Generic, Type, TypeVar

from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ztp2.db.models.base import ZTPBase

ModelType = TypeVar("ModelType", bound=ZTPBase)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


class CRUDBase(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    def __init__(self, schema: Type[ModelType]):
        self._schema = schema

    async def read(self, db: AsyncSession, id: Any) -> ModelType | None:
        statement = select(self._schema).where(self._schema.id == id)
        response = await db.execute(statement)
        target_obj = response.scalars().first()
        return target_obj

    async def read_all(self, db: AsyncSession, *,
                       skip: int = 0, limit: int = 100) -> list[ModelType]:
        statement = select(self._schema)\
            .order_by(self._schema.id.desc())\
            .offset(skip)\
            .limit(limit)
        response = await db.execute(statement)
        target_obj = response.scalars().all()
        return target_obj

    async def create(
            self,
            db: AsyncSession,
            *,
            obj_in: CreateSchemaType
    ) -> ModelType:
        obj_in_data = jsonable_encoder(obj_in)
        db_obj = self._schema(**obj_in_data)
        db.add(db_obj)
        await db.commit()
        return db_obj

    async def update(self, db: AsyncSession, *,
                     db_obj: ModelType,
                     obj_in: UpdateSchemaType | dict[str, Any]
    ) -> ModelType:
        obj_data = jsonable_encoder(db_obj)
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.dict(exclude_unset=True)
        for field in obj_data:
            if field in update_data:
                setattr(db_obj, field, update_data[field])
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def delete(self, db: AsyncSession, *, id: int) -> ModelType:
        statement = select(self._schema).filter_by(id=id)
        response = await db.execute(statement)
        target_obj = response.scalars().first()
        await db.delete(target_obj)
        await db.commit()
        return target_obj
