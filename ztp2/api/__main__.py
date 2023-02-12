from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine
from configargparse import ArgumentParser, ArgumentDefaultsHelpFormatter
import uvicorn

from .appbuilder import get_app
from .stub import ztp_db_session_stub
from .dependencies import get_db_session

ENV_VAR_PREFIX = 'ZTP_'


parser = ArgumentParser(
    auto_env_var_prefix=ENV_VAR_PREFIX, allow_abbrev=False,
    formatter_class=ArgumentDefaultsHelpFormatter,
    add_help=True,
)

group = parser.add_argument_group('Uvicorn')
group.add_argument('--unix-socket', help='Unix socket to run')
group.add_argument('--ip-address', help='IP address to serve')
group.add_argument('--port', help='Port to server')

group = parser.add_argument_group('Database')
group.add_argument('--database', help='Main ZTP database', required=True)


def main():
    args = parser.parse_args()

    app = get_app()

    main_database = args.database
    engine = create_async_engine(main_database)
    ztp_session = async_sessionmaker(engine,
                                     expire_on_commit=False,
                                     class_=AsyncSession)
    app.dependency_overrides[ztp_db_session_stub] = get_db_session(ztp_session)

    uvicorn_params = {'proxy_headers': True,
                      'forwarded_allow_ips': '*'}
    if args.unix_socket:
        uvicorn_params['uds'] = args.unix_socket
    else:
        uvicorn_params['host'] = args.ip_address or '127.0.0.1'
        uvicorn_params['port'] = args.port or 8000

    uvicorn.run(app=app, **uvicorn_params)
