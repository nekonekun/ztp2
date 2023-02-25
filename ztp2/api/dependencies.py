import aiohttp
from sqlalchemy.ext.asyncio import async_sessionmaker
from ..remote_apis.userside import UsersideAPI
from ..remote_apis.snmp import DeviceSNMP


def get_db_session(sessionmaker: async_sessionmaker):
    async def inner():
        async with sessionmaker() as session:
            yield session
    return inner


def get_userside_api(userside_api: UsersideAPI):
    async def inner():
        async with userside_api:
            yield userside_api
    return inner


def get_snmp_ro(community_ro: str):
    return DeviceSNMP(community=community_ro)


def get_http_session(url: str, **kwargs):
    async def inner():
        async with aiohttp.ClientSession(base_url=url, **kwargs) as session:
            yield session
    return inner
