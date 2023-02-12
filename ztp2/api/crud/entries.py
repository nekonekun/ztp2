from ...db.models.ztp import Entry
from ..schemas.entries import EntryCreateRequest, EntryPatchRequest
from .base import CRUDBase


class CRUDEntry(CRUDBase[Entry, EntryCreateRequest, EntryPatchRequest]):
    pass


entry = CRUDEntry(Entry)
