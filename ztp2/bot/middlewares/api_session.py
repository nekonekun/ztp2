import logging

from aiogram import BaseMiddleware
from aiogram.dispatcher.flags import get_flag, extract_flags
from aiogram.types import TelegramObject, Message
from typing import Callable, Awaitable, Any
from ..dependencies import ApiSessionFactory


class ApiSessionMiddleware(BaseMiddleware):
    def __init__(self, api_session_factory: ApiSessionFactory):
        super().__init__()
        self.api_session_factory = api_session_factory

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any]
    ) -> Any:
        is_using_api_session = get_flag(data, 'is_using_api_session')

        if not is_using_api_session:
            return await handler(event, data)

        async with self.api_session_factory() as api_session:
            middleware_data = data.copy()
            middleware_data['api_session'] = api_session
            return await handler(event, middleware_data)
