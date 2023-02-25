import aiogram
import aiohttp
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine


def sessionmaker_factory(database_url):
    def inner(*args):
        engine = create_async_engine(database_url)
        ztp_session_factory = async_sessionmaker(engine,
                                                 expire_on_commit=False,
                                                 class_=AsyncSession)
        return ztp_session_factory
    return inner


def netbox_session_factory(url: str, token: str):
    def inner(*args):
        headers = {'Authorization': f'Token {token}'}
        return aiohttp.ClientSession(url, headers=headers)
    return inner
