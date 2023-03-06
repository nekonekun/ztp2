from aiogram import BaseMiddleware
from aiogram.dispatcher.flags import get_flag
from aiogram.types import TelegramObject
from typing import Callable, Awaitable, Any
from ...remote_apis.userside import UsersideAPI


class UsersideMiddleware(BaseMiddleware):
    def __init__(self, userside_api: UsersideAPI):
        super().__init__()
        self.userside_api = userside_api

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any]
    ) -> Any:
        is_using_userside = get_flag(data, 'is_using_userside')

        if not is_using_userside:
            return await handler(event, data)

        async with self.userside_api:
            middleware_data = data.copy()
            middleware_data['userside_api'] = self.userside_api
            return await handler(event, middleware_data)
