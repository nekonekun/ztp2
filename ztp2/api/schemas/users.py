from pydantic import BaseModel


class UserCreateRequest(BaseModel):
    userside_id: int
    name: str
    telegram_id: int

    class Config:
        orm_mode = True


class UserPatchRequest(BaseModel):
    userside_id: int = None
    name: str = None
    telegram_id: int = None

    class Config:
        orm_mode = True


class User(BaseModel):
    id: int
    userside_id: int
    name: str
    telegram_id: int

    class Config:
        orm_mode = True
