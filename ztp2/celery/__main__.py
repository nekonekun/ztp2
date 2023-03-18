from configargparse import ArgumentParser, ArgumentDefaultsHelpFormatter
import celery

from .dependencies import sessionmaker_factory, netbox_session_factory
from .tasks.ztp import PreparedTask, RemoteFileModifyTask
from ..remote_apis.ftp import FtpFactory
from ..remote_apis.snmp import DeviceSNMP
from ..remote_apis.terminal import DeviceTerminal
from ..remote_apis.server import ServerTerminalFactory
from ..remote_apis.userside import UsersideAPI


ENV_VAR_PREFIX = 'ZTP_'

parser = ArgumentParser(
    auto_env_var_prefix=ENV_VAR_PREFIX, allow_abbrev=False,
    formatter_class=ArgumentDefaultsHelpFormatter,
    add_help=True,
)


def main():
    group = parser.add_argument_group('Celery')
    group.add_argument('--celery-broker', help='Broker URL', required=True)
    group.add_argument('--celery-result', help='Result backend', required=True)
    group.add_argument('--celery-hostname', help='Worker name', required=True)

    group = parser.add_argument_group('Database')
    group.add_argument('--database', help='Main ZTP database', required=True)

    group = parser.add_argument_group('Bot')
    group.add_argument('--bot-token', help='ZTP bot token', required=True)

    group = parser.add_argument_group('Netbox')
    group.add_argument('--netbox-url', help='Netbox URL', required=True)
    group.add_argument('--netbox-token', help='Netbox RW token', required=True)

    group = parser.add_argument_group('Userside')
    group.add_argument('--userside-url',
                       help='Userside URL (including api.php)', required=True)
    group.add_argument('--userside-key', help='Userside key', required=True)

    group = parser.add_argument_group('SNMP')
    group.add_argument('--snmp-community-rw',
                       help='SNMP RW community (private)',
                       required=True)

    group = parser.add_argument_group('Terminal')
    group.add_argument('--terminal-username', help='TACACS+ username',
                       required=True)
    group.add_argument('--terminal-password', help='TACACS+ password',
                       required=True)
    group.add_argument('--terminal-enable', help='TACACS+ enable password',
                       required=True)

    group = parser.add_argument_group('FTP')
    group.add_argument('--ftp-host', help='FTP server hostname', required=True)
    group.add_argument('--ftp-username', help='FTP username', required=True)
    group.add_argument('--ftp-password', help='FTP password', required=True)
    group.add_argument('--ftp-tftp-folder', help='Path to TFTP subdirectory',
                       required=True)
    group.add_argument('--ftp-configs-full-path',
                       help='Path to full configs subdirectory', required=True)

    group = parser.add_argument_group('DHCP server')
    group.add_argument('--office-dhcp-host', help='Office DHCP server hostname',
                       required=True)
    group.add_argument('--office-dhcp-username',
                       help='Office DHCP server username',
                       required=True)
    group.add_argument('--office-dhcp-password',
                       help='Office DHCP server password',
                       required=True)
    group.add_argument('--office-dhcp-filename',
                       help='Office DHCP server config filename',
                       required=True)

    args = parser.parse_args()
    app = celery.Celery(include=['ztp2.celery.tasks.ztp'],
                        broker=args.celery_broker,
                        backend=args.celery_result)
    app.conf.task_track_started = True
    app.conf.result_extended = True

    PreparedTask.sessionmaker_factory = sessionmaker_factory(args.database)

    PreparedTask.bot_token = args.bot_token

    PreparedTask.snmp_factory = DeviceSNMP(community=args.snmp_community_rw)

    PreparedTask.terminal_factory = DeviceTerminal(
        username=args.terminal_username,
        password=args.terminal_password,
        enable=args.terminal_enable)

    PreparedTask.netbox_factory = netbox_session_factory(args.netbox_url,
                                                         args.netbox_token)

    PreparedTask.userside_api = UsersideAPI(args.userside_url,
                                            args.userside_key)

    PreparedTask.ftp_factory = FtpFactory(args.ftp_host, args.ftp_username,
                                          args.ftp_password)

    PreparedTask.ftp_base_folder = args.ftp_tftp_folder
    PreparedTask.ftp_full_config_folder = args.ftp_configs_full_path

    RemoteFileModifyTask.server_ssh_factory = ServerTerminalFactory(
        ip_address=args.office_dhcp_host,
        username=args.office_dhcp_username,
        password=args.office_dhcp_password
    )
    RemoteFileModifyTask.remote_filename = args.office_dhcp_filename

    app.start(argv=['worker',
                    '--loglevel=debug',
                    '-E',
                    f'-n {args.celery_hostname}',
                    '--concurrency=4',
                    '--pool=prefork'
                    ])


def flower():
    group = parser.add_argument_group('Celery')
    group.add_argument('--celery-broker', help='Broker URL', required=True)
    group.add_argument('--celery-result', help='Result backend', required=True)

    args = parser.parse_args()
    app = celery.Celery(broker=args.celery_broker,
                        backend=args.celery_result)
    app.start(argv=['flower'])
