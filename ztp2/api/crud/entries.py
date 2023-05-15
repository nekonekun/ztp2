import ipaddress
from typing import Any
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import MACADDR
from sqlalchemy import select, cast, desc, insert
from sqlalchemy.orm import selectinload

from ...db.models.ztp import Entry
from ..schemas.entries import EntryCreateRequest, EntryPatchRequest
from .base import CRUDBase


class ConcreteCRUD(CRUDBase[Entry, EntryCreateRequest, EntryPatchRequest]):
    async def create(
            self,
            db: AsyncSession,
            *,
            obj_in: EntryCreateRequest
    ) -> Entry:
        obj_in_data = jsonable_encoder(obj_in)
        statement = insert(self._schema)
        statement = statement.values(**obj_in_data)
        statement = statement.returning(self._schema)
        statement = statement.options(selectinload(self._schema.model))
        statement = statement.options(selectinload(self._schema.employee))
        result = await db.execute(statement)
        await db.commit()
        return result.scalars().first()

    async def read(self, db: AsyncSession, id: Any):
        statement = select(self._schema).where(self._schema.id == id)
        statement = statement.options(selectinload(self._schema.model))
        statement = statement.options(selectinload(self._schema.employee))
        response = await db.execute(statement)
        target_obj = response.scalars().first()
        return target_obj

    async def read_by_clauses(self, db: AsyncSession, *,
                              employee_id: int = None,
                              status: str = None,
                              ip_address: ipaddress.IPv4Address = None,
                              mac_address: str = None,
                              serial_number: str = None,
                              task_id: int = None,
                              skip: int = 0, limit: int = 100) -> list[Entry]:
        statement = select(self._schema)
        if employee_id:
            statement = statement.where(self._schema.employee_id == employee_id)
        if status:
            statement = statement.where(self._schema.status == status)
        if ip_address:
            statement = statement.where(self._schema.ip_address == ip_address)
        if serial_number:
            statement = statement.where(
                self._schema.serial_number == serial_number)
        if mac_address:
            statement = statement.where(
                self._schema.mac_address == cast(mac_address, MACADDR))
        if task_id:
            statement = statement.where(self._schema.task_id == task_id)
        statement = statement.order_by(desc(self._schema.id))
        statement = statement.offset(skip).limit(limit)
        statement = statement.options(selectinload(self._schema.model))
        statement = statement.options(selectinload(self._schema.employee))
        response = await db.execute(statement)
        target_obj = response.scalars().all()
        return target_obj


entry = ConcreteCRUD(Entry)
