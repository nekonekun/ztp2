from fastapi import APIRouter, Depends
from ..crud import entry
from ..schemas.entries import Entry
from ..stub import ztp_db_session_stub

entries_router = APIRouter()


@entries_router.get('/', response_model=list[Entry])
async def entries_list(skip: int = 0,
                       limit: int = 100,
                       db=Depends(ztp_db_session_stub)):
    entries = await entry.read_multi(db,
                                     skip=skip,
                                     limit=limit,)
    return entries
