from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine
from celery import Celery
from configargparse import ArgumentParser, ArgumentDefaultsHelpFormatter
import uvicorn

from .appbuilder import get_app
from .stub import ztp_db_session_stub, userside_api_stub, snmp_ro_stub, \
    netbox_session_stub, celery_stub
from .dependencies import get_db_session, get_userside_api, get_snmp_ro, \
    get_http_session, get_celery_instance
from ..remote_apis.userside import UsersideAPI

ENV_VAR_PREFIX = 'ZTP_'


parser = ArgumentParser(
    auto_env_var_prefix=ENV_VAR_PREFIX, allow_abbrev=False,
    formatter_class=ArgumentDefaultsHelpFormatter,
    add_help=True,
)

group = parser.add_argument_group('Uvicorn')
group.add_argument('--unix-socket', help='Unix socket to run')
group.add_argument('--ip-address', help='IP address to serve '
                                        '(will be ignored if unix socket '
                                        'is specified)')
group.add_argument('--port', help='Port to server')

group = parser.add_argument_group('Database')
group.add_argument('--database', help='Main ZTP database', required=True)

group = parser.add_argument_group('Userside')
group.add_argument('--userside-url', help='Userside URL (including api.php)',
                   required=True)
group.add_argument('--userside-key', help='Userside key', required=True)

group = parser.add_argument_group('Netbox')
group.add_argument('--netbox-url', help='Netbox URL', required=True)
group.add_argument('--netbox-token', help='Netbox RW token', required=True)

group = parser.add_argument_group('Devices access')
group.add_argument('--snmp-community-ro', help='SNMP readonly community',
                   required=True)

group = parser.add_argument_group('Celery')
group.add_argument('--celery-broker', help='Broker URL', required=True)
group.add_argument('--celery-result', help='Result backend', required=True)


def main():
    args = parser.parse_args()

    app = get_app()

    main_database = args.database
    engine = create_async_engine(main_database)
    ztp_session = async_sessionmaker(engine,
                                     expire_on_commit=False,
                                     class_=AsyncSession)
    app.dependency_overrides[ztp_db_session_stub] = get_db_session(ztp_session)

    userside_url = args.userside_url
    userside_key = args.userside_key
    userside_api = UsersideAPI(userside_url, userside_key)
    app.dependency_overrides[userside_api_stub] = get_userside_api(userside_api)

    snmp_community = args.snmp_community_ro
    app.dependency_overrides[snmp_ro_stub] = lambda: get_snmp_ro(snmp_community)

    netbox_url = args.netbox_url
    netbox_token = args.netbox_token
    headers = {'Authorization': f'Token {netbox_token}'}
    app.dependency_overrides[netbox_session_stub] = get_http_session(
        netbox_url, headers=headers)

    celery = Celery(broker=args.celery_broker, backend=args.celery_result)
    celery.conf.task_track_started = True
    celery.conf.result_extended = True
    app.dependency_overrides[celery_stub] = get_celery_instance(celery)

    uvicorn_params = {'proxy_headers': True,
                      'forwarded_allow_ips': '*'}
    if args.unix_socket:
        uvicorn_params['uds'] = args.unix_socket
    else:
        uvicorn_params['host'] = args.ip_address or '127.0.0.1'
        uvicorn_params['port'] = args.port or 8000

    uvicorn.run(app=app, **uvicorn_params)
