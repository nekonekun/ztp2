from fastapi import APIRouter, Depends
from .. import crud
from ..schemas.models import Model, ModelCreateRequest, ModelPatchRequest
from ..stub import ztp_db_session_stub

models_router = APIRouter()


@models_router.get('/', response_model=list[Model])
async def models_list(skip: int = 0,
                      limit: int = 100,
                      model: str = None,
                      db=Depends(ztp_db_session_stub)):
    if model:
        models = await crud.model.read_by_model(db, model=model)
    else:
        models = await crud.model.read_all(db, skip=skip, limit=limit)
    return models


@models_router.post('/', response_model=Model)
async def models_create(req: ModelCreateRequest,
                        db=Depends(ztp_db_session_stub)):
    answer = await crud.model.create(db, obj_in=req)
    return answer


@models_router.get('/{model_id}/', response_model=Model)
async def models_read(model_id: int, db=Depends(ztp_db_session_stub)):
    entry = await crud.model.read(db=db, id=model_id)
    return entry


@models_router.patch('/{model_id}/', response_model=Model)
async def models_partial_update(model_id: int, req: ModelPatchRequest,
                                db=Depends(ztp_db_session_stub)):
    model = await crud.model.read(db=db, id=model_id)
    answer = await crud.entry.update(db=db, db_obj=model, obj_in=req)
    return answer


@models_router.delete('/{model_id}/', response_model=Model)
async def models_delete(model_id: int, db=Depends(ztp_db_session_stub)):
    answer = await crud.model.remove(db, id=model_id)
    return answer
