import aiohttp
import aiosnmp.exceptions
import asyncio
from celery import Task, current_app
from multiprocessing import Lock
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker
from typing import Callable

from ..progress import Progresser
from ...db.models.ztp import Entry
from ...remote_apis.snmp import DeviceSNMP
from ...remote_apis.terminal import DeviceTerminal
from ...remote_apis.ftp import ContextedFTP
from ...utils.ftp import pattern_in_file_content
from ...utils.netbox import get_prefix_info
from ...utils.ztp import CiscoInterface, DlinkInterface
from ...utils.server import create_entry, change_ip_address, change_mac_address
from ...utils.sort_of_ping import check_port


SNMP_DEVICE_PATTERNS = ['DES-', 'DGS-12', 'DGS-30', 'Extreme']
CISCO_DEVICE_PATTERNS = ['Cisco']
ALL_DEVICE_PATTERNS = SNMP_DEVICE_PATTERNS + CISCO_DEVICE_PATTERNS

CHECK_DELAY = 5
DEVICE_DHCP_DELAY = 5
HUMAN_CONFIGURE_KNOWN_PORT_TIME = 60
HUMAN_FIND_AND_CONFIGURE_PORT_TIME = 90
TFTP_LOG_FILENAME = '/tftp/tftp.log'
DLINK_FIRMWARE_UPDATE_TIME = 195

def stub(*args, **kwargs):  # noqa
    raise NotImplementedError


class PreparedTask(Task):  # noqa
    sessionmaker_factory = stub
    terminal_factory = stub
    snmp_factory = stub
    bot_token = stub
    netbox_factory = stub
    ftp_factory = stub
    loop: asyncio.BaseEventLoop | None = stub

    def before_start(self, task_id, args, kwargs):
        PreparedTask.loop = asyncio.new_event_loop()

    def after_return(self, status, retval, task_id, args, kwargs, einfo):
        PreparedTask.loop.close()


class RemoteFileModifyTask(Task):  # noqa
    lock = Lock()
    server_ssh_factory = stub
    remote_filename = stub

    def before_start(self, task_id, args, kwargs):
        self.lock.acquire()

    def after_return(self, status, retval, task_id, args, kwargs, einfo):
        self.lock.release()


@current_app.task(base=PreparedTask, name='ztp2_main', bind=True)
def ztp(self, ztp_id: int, sender_chat_id: int):  # noqa
    ztp.loop.run_until_complete(_ztp(ztp_id,
                                     sender_chat_id,
                                     ztp.sessionmaker_factory(),
                                     ztp.snmp_factory,
                                     ztp.terminal_factory,
                                     ztp.netbox_factory,
                                     ztp.bot_token,
                                     ztp.ftp_factory))


async def _ztp(ztp_id: int,
               sender_chat_id: int,
               sessionmaker: async_sessionmaker,
               snmp: DeviceSNMP,
               terminal: DeviceTerminal,
               netbox_factory: Callable[[], aiohttp.ClientSession],
               bot_token: str,
               tftp_factory: Callable[[], ContextedFTP]):
    progresser = Progresser(bot_token, sender_chat_id)
    progresser.startup()
    await progresser.greet(f'Свич {ztp_id}')
    await progresser.send_step('Бот смотрит в базу')
    async with sessionmaker() as session:
        statement = select(Entry).where(Entry.id == ztp_id)
        response = await session.execute(statement)
        entry = response.scalars().first()
    progresser.update_done(f'Бот посмотрел данные свича {entry.ip_address}')
    async with netbox_factory() as session:
        answer = await get_prefix_info(entry.ip_address.exploded,
                                       session)
    management_vlan_id = answer['vlan']['vid']
    progresser.update_done(f'Бот определил тег менеджмент влана: '
                           f'{management_vlan_id}')
    if entry.autochange_vlans:
        manual_vlan_change = False
        await progresser.send_step(f'Бот смотрит модель вышестоящего '
                                   f'{entry.parent_switch}')
        try:
            async with snmp(entry.parent_switch.exploded) as session:
                response = await session.get('1.3.6.1.2.1.1.1.0')
        except aiosnmp.exceptions.SnmpTimeoutError:
            manual_vlan_change = True
            progresser.update_done(f'Бот не смог узнать модель вышестоящего '
                                   f'{entry.parent_switch}')
            await progresser.send_step('Человек настраивает аплинк')
            await progresser.alert(f'@nekone подорвись и настрой '
                                   f'{entry.parent_switch} : '
                                   f'{entry.parent_port}')
            await asyncio.sleep(HUMAN_CONFIGURE_KNOWN_PORT_TIME)
            progresser.update_done('Человек нашел и настроил аплинк '
                                   '(скорее всего)')
        else:
            model = response[0].value.decode('utf-8')
            progresser.update_done(f'Бот узнал модель вышестоящего '
                                   f'{entry.parent_switch}: {model}')
            if all(pattern not in model for pattern in ALL_DEVICE_PATTERNS):
                manual_vlan_change = True
                await progresser.send_step('Человек настраивает аплинк')
                await progresser.alert(f'@nekone подорвись и настрой '
                                       f'{entry.parent_switch} : '
                                       f'{entry.parent_port}')
                await asyncio.sleep(HUMAN_CONFIGURE_KNOWN_PORT_TIME)
                progresser.update_done('Человек нашел и настроил аплинк '
                                       '(скорее всего)')
            else:
                await progresser.send_step(f'Бот смотрит антаги на '
                                           f'{entry.parent_switch} : '
                                           f'{entry.parent_port}')
                if any(pattern in model for pattern in SNMP_DEVICE_PATTERNS):
                    uplink_interface = DlinkInterface(
                        entry.parent_switch.exploded,
                        entry.parent_port,
                        management_vlan_id,
                        snmp
                    )
                else:  # pattern in model for pattern in CISCO_DEVICE_PATTERNS
                    uplink_interface = CiscoInterface(
                        entry.parent_switch.exploded,
                        entry.parent_port,
                        management_vlan_id,
                        terminal(entry.parent_switch.exploded,
                                 'AsyncIOSXEDriver',
                                 transport='asynctelnet')
                    )
                async with uplink_interface:
                    untagged = await uplink_interface.get_untagged()
                if isinstance(untagged, list):
                    untagged_text = ', '.join(map(str, untagged))
                else:
                    untagged_text = untagged
                if not untagged_text:
                    untagged_text = 'их нет'
                progresser.update_done(f'Бот посмотрел антаги на '
                                       f'{entry.parent_switch} : '
                                       f'{entry.parent_port} '
                                       f'[{untagged_text}]')
                await progresser.send_step('Бот перенастраивает вышестоящий')
                async with uplink_interface:
                    await uplink_interface.switch_to_management()
                progresser.update_done('Бот перенастроил вышестоящий')
    else:
        await progresser.send_step('Человек ищет и настраивает аплинк')
        await progresser.alert(f'@nekone найди и настрой, ага?')
        await asyncio.sleep(HUMAN_FIND_AND_CONFIGURE_PORT_TIME)
        progresser.update_done('Человек нашел и настроил аплинк (скорее всего)')

    await progresser.send_step('Свич получает IP и опции по DHCP')
    while not await check_port(entry.ip_address.exploded):
        await asyncio.sleep(CHECK_DELAY)
    progresser.update_done('Свич начал пинговаться')

    await progresser.send_step('Свич запрашивает прошивку')
    await asyncio.sleep(DEVICE_DHCP_DELAY)
    firmware_requested_pattern = f'RRQ from {entry.ip_address.exploded} ' \
                                 f'filename firmwares'
    async with tftp_factory() as ftp_client:
        while not await pattern_in_file_content(TFTP_LOG_FILENAME,
                                                firmware_requested_pattern,
                                                ftp_client):
            await asyncio.sleep(CHECK_DELAY)
    progresser.update_done('Свич запросил прошивку')

    await progresser.send_step('Свич качает прошивку и шьётся')
    await asyncio.sleep(DLINK_FIRMWARE_UPDATE_TIME)
    ztp_froze = False
    config_requested_pattern = f'RRQ from {entry.ip_address.exploded} ' \
                               f'filename configs'
    async with tftp_factory() as ftp_client:
        if not await pattern_in_file_content(TFTP_LOG_FILENAME,
                                             config_requested_pattern,
                                             ftp_client):
            await progresser.send_step('Свич завис, надо зайти и выйти')
            ztp_froze = True
            while not await pattern_in_file_content(TFTP_LOG_FILENAME,
                                                    config_requested_pattern,
                                                    ftp_client):
                await asyncio.sleep(CHECK_DELAY)
            progresser.update_done('Свич скачал прошивку, прошился, '
                                   'скачал конфиг и ребутнулся')
        else:
            progresser.update_done('Свич скачал прошивку, прошился, '
                                   'и скачал конфиг ')

    if entry.autochange_vlans:
        if manual_vlan_change:  # noqa
            await progresser.send_step('Человек настраивает аплинк')
            await progresser.alert(f'@nekone подорвись и настрой '
                                   f'{entry.parent_switch} : '
                                   f'{entry.parent_port}')
            await asyncio.sleep(HUMAN_CONFIGURE_KNOWN_PORT_TIME)
            progresser.update_done('Человек нашел и настроил аплинк '
                                   '(скорее всего)')
        else:
            await progresser.send_step('Бот перенастраивает вышестоящий')
            async with uplink_interface:  # noqa
                await uplink_interface.switch_back()  # noqa
            progresser.update_done('Бот перенастроил вышестоящий')
    else:
        await progresser.send_step('Человек ищет и настраивает аплинк')
        await progresser.alert(f'@nekone найди и настрой, ага?')
        await asyncio.sleep(HUMAN_FIND_AND_CONFIGURE_PORT_TIME)
        progresser.update_done('Человек нашел и настроил аплинк (скорее всего)')

    if not ztp_froze:
        await progresser.send_step('Свич ребутается после скачивания конфига')
    while not await check_port(entry.ip_address.exploded):
        await asyncio.sleep(CHECK_DELAY)
    progresser.update_done('Свич начал пинговаться')

    await progresser.finish('Готово')
    await progresser.shutdown()


@current_app.task(base=RemoteFileModifyTask, name='ztp2_office_dhcp', bind=True)
def create_dhcp_office_entry(self, entry_id: int, mac_address: str,
                             ftp_host: str, config_filename: str,
                             firmware_filename: str):
    mac_address = ''.join(
        filter(lambda x: x in '0123456789abcdef', mac_address.lower())
    )
    mac_address = [mac_address[i:i+2] for i in range(0, len(mac_address), 2)]
    mac_address = ':'.join(mac_address)
    with self.server_ssh_factory() as session:
        create_entry(entry_id, mac_address, ftp_host, config_filename,
                     firmware_filename, self.remote_filename, session)


@current_app.task(base=RemoteFileModifyTask,
                  name='ztp2_office_dhcp_edit',
                  bind=True)
def edit_dhcp_office_entry(self, entry_id: int, field: str, value: str):
    if field not in ['ip_address', 'mac_address']:
        return
    with self.server_ssh_factory() as session:
        if field == 'ip_address':
            change_ip_address(entry_id, value, self.remote_filename, session)
        elif field == 'mac_address':
            change_mac_address(entry_id, value, self.remote_filename, session)
