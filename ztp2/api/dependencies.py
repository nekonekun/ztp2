import aiohttp
from celery import Celery
from sqlalchemy.ext.asyncio import async_sessionmaker
from ..remote_apis.userside import UsersideAPI
from ..remote_apis.snmp import DeviceSNMP
from ..remote_apis.ftp import ContextedFTP


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
    def inner():
        return DeviceSNMP(community=community_ro)
    return inner


def get_contexted_ftp_instance(host: str, username: str, password: str):
    def inner():
        return ContextedFTP(host, username, password)
    return inner


def get_http_session(url: str, **kwargs):
    async def inner():
        async with aiohttp.ClientSession(base_url=url, **kwargs) as session:
            yield session
    return inner


def get_celery_instance(celery: Celery):
    def inner():
        return celery
    return inner
