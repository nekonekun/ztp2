import logging

from aiogram import BaseMiddleware
from aiogram.dispatcher.flags import get_flag
from aiogram.types import Message
from typing import Callable, Awaitable, Any
from ..dependencies import ApiSessionFactory


class AuthMiddleware(BaseMiddleware):
    def __init__(self, api_session_factory: ApiSessionFactory):
        super().__init__()
        self.api_session_factory = api_session_factory

    async def __call__(
        self,
        handler: Callable[[Message, dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: dict[str, Any]
    ) -> Any:
        authorization = get_flag(data, 'authorization')

        if not authorization:
            return await handler(event, data)

        async with self.api_session_factory() as api_session:
            async with api_session.get('/users/', params={
                'telegram_id': event.from_user.id
            }) as response:
                content = await response.json()
        if not content:
            logging.error('Unauthorized access attempt')
            return
        current_user = content[0]
        middleware_data = data.copy()
        middleware_data['current_user'] = current_user
        return await handler(event, middleware_data)
