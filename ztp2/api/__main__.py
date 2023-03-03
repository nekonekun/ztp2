from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine
from celery import Celery
from configargparse import ArgumentParser, ArgumentDefaultsHelpFormatter
import uvicorn

from .appbuilder import get_app
from .dependencies import get_db_session, get_userside_api, get_snmp_ro, \
    get_http_session, get_celery_instance, get_contexted_ftp_instance
from .settings import FtpSettings
from .stub import ztp_db_session_stub, userside_api_stub, snmp_ro_stub, \
    netbox_session_stub, celery_stub, kea_db_session_stub, ftp_settings_stub, \
    contexted_ftp_stub

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

group = parser.add_argument_group('DHCP database')
group.add_argument('--dhcp-database', help='KEA DHCP database', required=True)

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

group = parser.add_argument_group('FTP')
group.add_argument('--ftp-host', help='FTP host', required=True)
group.add_argument('--ftp-username', help='FTP username', required=True)
group.add_argument('--ftp-password', help='FTP password', required=True)
group.add_argument('--ftp-tftp-folder', help='Path to TFTP subdirectory',
                   required=True)
group.add_argument('--ftp-templates-initial-path',
                   help='Path to initial templates subdirectory', required=True)
group.add_argument('--ftp-templates-full-path',
                   help='Path to full templates subdirectory', required=True)
group.add_argument('--ftp-configs-initial-path',
                   help='Path to initial configs subdirectory', required=True)
group.add_argument('--ftp-configs-full-path',
                   help='Path to full configs subdirectory', required=True)
group.add_argument('--ftp-firmwares-path',
                   help='Path to firmwares subdirectory', required=True)


def main():
    args = parser.parse_args()

    app = get_app()

    main_database = args.database
    ztp_engine = create_async_engine(main_database)
    ztp_session = async_sessionmaker(ztp_engine,
                                     expire_on_commit=False,
                                     class_=AsyncSession)
    app.dependency_overrides[ztp_db_session_stub] = get_db_session(ztp_session)

    kea_database = args.dhcp_database
    kea_engine = create_async_engine(kea_database)
    kea_session = async_sessionmaker(kea_engine,
                                     expire_on_commit=False,
                                     class_=AsyncSession)
    app.dependency_overrides[kea_db_session_stub] = get_db_session(kea_session)

    userside_url = args.userside_url
    userside_key = args.userside_key
    userside_api = UsersideAPI(userside_url, userside_key)
    app.dependency_overrides[userside_api_stub] = get_userside_api(userside_api)

    snmp_community = args.snmp_community_ro
    app.dependency_overrides[snmp_ro_stub] = get_snmp_ro(snmp_community)

    netbox_url = args.netbox_url
    netbox_token = args.netbox_token
    headers = {'Authorization': f'Token {netbox_token}'}
    app.dependency_overrides[netbox_session_stub] = get_http_session(
        netbox_url, headers=headers)

    celery = Celery(broker=args.celery_broker, backend=args.celery_result)
    celery.conf.task_track_started = True
    celery.conf.result_extended = True
    app.dependency_overrides[celery_stub] = get_celery_instance(celery)

    ftp_settings = FtpSettings(
        args.ftp_host, args.ftp_tftp_folder, args.ftp_templates_initial_path,
        args.ftp_templates_full_path, args.ftp_configs_initial_path,
        args.ftp_configs_full_path, args.ftp_firmwares_path
    )
    app.dependency_overrides[ftp_settings_stub] = lambda: ftp_settings
    app.dependency_overrides[contexted_ftp_stub] = get_contexted_ftp_instance(
        args.ftp_host, args.ftp_username, args.ftp_password)

    uvicorn_params = {'proxy_headers': True,
                      'forwarded_allow_ips': '*'}
    if args.unix_socket:
        uvicorn_params['uds'] = args.unix_socket
    else:
        uvicorn_params['host'] = args.ip_address or '127.0.0.1'
        uvicorn_params['port'] = args.port or 8000

    uvicorn.run(app=app, **uvicorn_params)
