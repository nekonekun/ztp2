from fastapi import APIRouter, Depends

from .. import crud
from ..schemas.users import User, UserCreateRequest, UserPatchRequest
from ..stub import ztp_db_session_stub

users_router = APIRouter()


@users_router.post('/', response_model=User | None)
async def users_create(req: UserCreateRequest,
                       db=Depends(ztp_db_session_stub)):
    answer = await crud.user.create(db, obj_in=req)
    return answer


@users_router.get('/', response_model=list[User])
async def users_list(skip: int = 0,
                     limit: int = 100,
                     userside_id: int = None,
                     name: str = None,
                     telegram_id: int = None,
                     db=Depends(ztp_db_session_stub)):
    entries = await crud.user.read_by_clauses(db, userside_id=userside_id,
                                              name=name,
                                              telegram_id=telegram_id,
                                              skip=skip, limit=limit)
    return entries


@users_router.get('/{user_id}/', response_model=User | None)
async def users_read(user_id: int, db=Depends(ztp_db_session_stub)):
    user = await crud.entry.read(db=db, id=user_id)
    return user


@users_router.patch('/{user_id}/', response_model=User)
async def users_partial_update(user_id: int, req: UserPatchRequest,
                               db=Depends(ztp_db_session_stub)):
    user = await crud.user.read(db=db, id=user_id)
    answer = await crud.user.update(db=db, db_obj=user, obj_in=req)
    return answer


@users_router.delete('/{user_id}/')
async def users_delete(user_id: int, db=Depends(ztp_db_session_stub)):
    answer = await crud.user.delete(db, id=user_id)
    return answer
