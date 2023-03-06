from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
import asyncio
from configargparse import ArgumentParser, ArgumentDefaultsHelpFormatter
import logging

from .dependencies import ApiSessionFactory
from .middlewares import ApiSessionMiddleware, AuthMiddleware, \
    UsersideMiddleware
from .routers import manage_router, add_router
from ..remote_apis.userside import UsersideAPI

logging.basicConfig(level=logging.INFO)


ENV_VAR_PREFIX = 'ZTP_'


parser = ArgumentParser(
    auto_env_var_prefix=ENV_VAR_PREFIX, allow_abbrev=False,
    formatter_class=ArgumentDefaultsHelpFormatter,
    add_help=True,
)

group = parser.add_argument_group('Bot')
group.add_argument('--bot-token', help='ZTP bot token', required=True)

group = parser.add_argument_group('API')
group.add_argument('--unix-socket', help='API unix socket ')
group.add_argument('--ip-address', help='API IP address')
group.add_argument('--port', help='API port')

group = parser.add_argument_group('Userside')
group.add_argument('--userside-url', help='Userside URL (including api.php)',
                   required=True)
group.add_argument('--userside-key', help='Userside key', required=True)


def main():
    args = parser.parse_args()
    token = args.bot_token
    if args.unix_socket:
        api_session_factory = ApiSessionFactory(
            unix_socket=args.unix_socket)
    else:
        ip_address = args.ip_address or '127.0.0.1'
        port = args.port or 8000
        base_url = f'http://{ip_address}:{port}/'
        api_session_factory = ApiSessionFactory(base_url=base_url)

    userside_url = args.userside_url
    userside_key = args.userside_key
    userside_api = UsersideAPI(userside_url, userside_key)

    asyncio.run(bot_main(token=token,
                         api_session_factory=api_session_factory,
                         userside_api=userside_api))


async def bot_main(token: str, api_session_factory: ApiSessionFactory,
                   userside_api: UsersideAPI):
    bot = Bot(token=token, parse_mode='html')
    dp = Dispatcher(storage=MemoryStorage())

    dp.include_router(manage_router)
    dp.include_router(add_router)

    dp.message.middleware(ApiSessionMiddleware(api_session_factory))
    dp.callback_query.middleware(ApiSessionMiddleware(api_session_factory))
    dp.message.middleware(AuthMiddleware(api_session_factory))
    dp.message.middleware(UsersideMiddleware(userside_api))

    await dp.start_polling(bot)
