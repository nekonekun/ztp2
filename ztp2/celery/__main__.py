from configargparse import ArgumentParser, ArgumentDefaultsHelpFormatter
import celery

from .dependencies import sessionmaker_factory, netbox_session_factory
from .tasks.ztp import PreparedTask
from ..remote_apis.ftp import FtpFactory
from ..remote_apis.snmp import DeviceSNMP
from ..remote_apis.terminal import DeviceTerminal


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

    args = parser.parse_args()
    app = celery.Celery(include=['ztp2.celery.tasks.ztp'],
                        broker=args.celery_broker,
                        backend=args.celery_result)

    PreparedTask.sessionmaker_factory = sessionmaker_factory(args.database)

    PreparedTask.bot_token = args.bot_token

    PreparedTask.snmp_factory = DeviceSNMP(community=args.snmp_community_rw)

    PreparedTask.terminal_factory = DeviceTerminal(
        username=args.terminal_username,
        password=args.terminal_password,
        enable=args.terminal_enable)

    PreparedTask.netbox_factory = netbox_session_factory(args.netbox_url,
                                                         args.netbox_token)

    PreparedTask.ftp_factory = FtpFactory(args.ftp_host, args.ftp_username,
                                          args.ftp_password)

    app.start(argv=['worker',
                    '--loglevel=debug',
                    '-E',
                    f'-n {args.celery_hostname}',
                    ])


def flower():
    group = parser.add_argument_group('Celery')
    group.add_argument('--celery-broker', help='Broker URL', required=True)
    group.add_argument('--celery-result', help='Result backend', required=True)

    args = parser.parse_args()
    app = celery.Celery(broker=args.celery_broker,
                        backend=args.celery_result)
    app.start(argv=['flower'])
