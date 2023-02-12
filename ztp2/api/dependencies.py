from sqlalchemy.ext.asyncio import async_sessionmaker


def get_db_session(sessionmaker: async_sessionmaker):
    async def inner():
        session = sessionmaker()
        try:
            yield session
        finally:
            await session.close()
    return inner
