from pydantic import BaseModel
from typing import Any


class TaskCreateRequest(BaseModel):
    name: str
    args: list
    kwargs: dict


class TaskCreateResponse(BaseModel):
    task_id: str


class Task(BaseModel):
    task_id: str
    name: str | None
    status: str | None
    args: list[Any] | None
    kwargs: dict[Any, Any] | None
    info: dict[Any, Any] | None
