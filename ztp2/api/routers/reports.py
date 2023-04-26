from fastapi import APIRouter, Depends
from ..stub import ztp_db_session_stub, userside_api_stub
from .. import crud
from ... import utils

reports_router = APIRouter()


@reports_router.get('/commissioning/{task_id}/')
async def commissioning_report(task_id: int,
                               db=Depends(ztp_db_session_stub),
                               userside_api=Depends(userside_api_stub)):
    entries = await crud.entry.read_by_clauses(db, task_id=task_id)
    # ZTP ID | IP | SN | Имя Бокса | id Бокса | Модель коммутатора
    entries = [
        {'ztp_id': entry.id,
         'ip_address': entry.ip_address.exploded,
         'serial_number': entry.serial_number,
         'mac_address': entry.mac_address,
         'box_name': (await utils.userside.get_node_name(
             entry.node_id, userside_api)).replace(
             'Россия, Санкт-Петербург, ', ''),
         'model': entry.model.model,
         'employee': ', '.join(entry.employee.name.split(' ')[:2])}
        for entry in entries
    ]
    return entries
