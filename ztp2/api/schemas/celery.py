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
    name: str
    status: str | None
    args: list[Any]
    kwargs: dict[Any, Any]
    info: dict[Any, Any]
