from ...db.models.ztp import Model
from ..schemas.models import ModelCreateRequest, ModelPatchRequest
from .base import CRUDBase


class CRUDEntry(CRUDBase[Model, ModelCreateRequest, ModelPatchRequest]):
    pass


model = CRUDEntry(Model)