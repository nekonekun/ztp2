from fastapi import APIRouter, Depends
from ..crud import model
from ..schemas.models import Model
from ..stub import ztp_db_session_stub

models_router = APIRouter()


@models_router.get('/', response_model=list[Model])
async def models_list(skip: int = 0,
                      limit: int = 100,
                      db=Depends(ztp_db_session_stub)):
    models = await model.read_multi(db,
                                    skip=skip,
                                    limit=limit,)
    return models
