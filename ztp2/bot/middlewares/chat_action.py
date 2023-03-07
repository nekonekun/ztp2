from aiogram import BaseMiddleware
from aiogram.dispatcher.flags import get_flag
from aiogram.types import Message, TelegramObject, CallbackQuery
from aiogram.utils.chat_action import ChatActionSender
from typing import Callable, Awaitable, Any


class ChatActionMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any]
    ) -> Any:
        long_operation_type = get_flag(data, 'long_operation')

        if not long_operation_type:
            return await handler(event, data)
        if isinstance(event, Message):
            chat_id = event.chat.id
        elif isinstance(event, CallbackQuery):
            chat_id = event.message.chat.id
        else:
            return await handler(event, data)
        async with ChatActionSender(
                action=long_operation_type,
                chat_id=chat_id
        ):
            return await handler(event, data)
