import aiohttp
import aiosnmp.exceptions
import asyncio
from celery import Task, current_app
from multiprocessing import Lock
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker
from typing import Callable

from ..progress import Progresser
from ...db.models.ztp import Entry, Model
from ...remote_apis.snmp import DeviceSNMP
from ...remote_apis.terminal import DeviceTerminal
from ...remote_apis.ftp import ContextedFTP
from ...remote_apis.userside import UsersideAPI
from ...utils.ftp import pattern_in_file_content, get_file_content
from ...utils.netbox import get_prefix_info, mark_ip_active
from ...utils.ztp import CiscoInterface, DlinkInterface
from ...utils.server import create_entry, change_ip_address, change_mac_address
from ...utils.sort_of_ping import check_port
from ...utils.ping import check
from ...utils.terminal import extract_dlink_serial
from ...utils.userside import transfer_inventory_to_employee, \
    get_inventory_item, transfer_inventory_to_node, update_commutation, \
    update_up_down_link

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
    userside_api = stub
    ftp_factory = stub
    ftp_base_folder = stub
    ftp_full_config_folder = stub
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
    while not await check(entry.ip_address.exploded):
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
    while not await check(entry.ip_address.exploded):
        await asyncio.sleep(CHECK_DELAY)
    progresser.update_done('Свич начал пинговаться')

    await progresser.finish('Готово')
    await progresser.shutdown()


@current_app.task(base=RemoteFileModifyTask, name='ztp2_office_dhcp', bind=True)
def create_dhcp_office_entry(self, entry_id: int, mac_address: str,
                             ftp_host: str, config_filename: str,
                             firmware_filename: str):
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


@current_app.task(base=PreparedTask, name='ztp2_finalize', bind=True)
def finalize(self, ztp_id: int, sender_chat_id: int):
    full_configs_path = self.ftp_base_folder + self.ftp_full_config_folder
    self.loop.run_until_complete(_finalize(ztp_id,
                                           sender_chat_id,
                                           self.bot_token,
                                           self.sessionmaker_factory(),
                                           self.terminal_factory,
                                           self.ftp_factory,
                                           full_configs_path,
                                           self.netbox_factory,
                                           self.userside_api))


async def _finalize(ztp_id: int,
                    sender_chat_id: int,
                    bot_token: str,
                    sessionmaker: async_sessionmaker,
                    terminal_factory: DeviceTerminal,
                    ftp_factory: Callable[[], ContextedFTP],
                    configs_tftp_path: str,
                    netbox_factory: Callable[[], aiohttp.ClientSession],
                    userside_api: UsersideAPI):
    # Получить информацию о свиче
    progresser = Progresser(bot_token, sender_chat_id)
    progresser.startup()
    await progresser.greet(f'Свич {ztp_id}')
    await progresser.send_step('Смотрим в базу')
    async with sessionmaker() as session:
        statement = select(Entry).where(Entry.id == ztp_id)
        response = await session.execute(statement)
        entry = response.scalars().first()
    progresser.update_done(f'Узнали IP: {entry.ip_address}')

    # Пингануть свич
    await progresser.send_step('Проверяем, что свич пингуется')
    if not await check(entry.ip_address.exploded):
        progresser.update_done('Свич не пингуется на момент запуска команды')
        await progresser.finish('Провалено')
        await progresser.shutdown()
        return
    progresser.update_done('Свич пингуется на момент запуска команды')

    # Проверить серийный номер
    await progresser.send_step('Проверяем серийный номер')
    session = terminal_factory(entry.ip_address.exploded, 'dlink_os')
    async with session:
        serial_number = await extract_dlink_serial(session)
    if entry.serial_number != serial_number:
        progresser.update_done('Серийный номер в базе и на свиче не совпадают')
        await progresser.finish('Провалено')
        await progresser.shutdown()
        return
    progresser.update_done('Серийный номер в базе и на железе совпадает')

    # Получить конфиг
    await progresser.send_step('Получаем конфиг')
    async with ftp_factory() as ftp_client:
        filename = configs_tftp_path + entry.ip_address.exploded + '.cfg'
        cfg = await get_file_content(filename, ftp_client)
    cfg = list(filter(lambda x: x, cfg.split('\n')))
    line_count = len(cfg)
    progresser.update_done(f'Получен конфиг из {line_count} строк')

    # Отправить конфиг построчно
    await progresser.send_step('Отправляем конфиг на свич')
    session = terminal_factory(entry.ip_address.exploded, 'dlink_os')
    async with session:
        alert_chunks = 5
        threshold = line_count // alert_chunks
        percents = 100 // alert_chunks
        multiplier = 1
        for index, line in enumerate(cfg):
            if index > threshold * multiplier:
                percents_done = percents * multiplier
                await progresser.send_step('Отправляем конфиг на свич '
                                           f'(отправлено {percents_done}%)')
                multiplier += 1
            await session.send_command(line)
    progresser.update_done('Отправили конфиг на свич')

    # Проверить что свич пингуется после заливки конфига
    await progresser.send_step('Проверяем, что свич пингуется')
    if not await check(entry.ip_address.exploded):
        progresser.update_done('Свич не пингуется после заливки конфига')
        await progresser.finish('Провалено')
        await progresser.shutdown()
        return
    progresser.update_done('Свич пингуется после заливки конфига')

    # Исправить netbox, пометить айпишник Active
    await progresser.send_step('Смотрим в Netbox')
    async with netbox_factory() as session:
        await mark_ip_active(entry.ip_address.exploded, session)
    progresser.update_done('Установили статус IP адреса в Netbox\'е')

    # Получить девайс в юзерсайде
    await progresser.send_step('Ищем свич с таким IP адресом в Usersid\'е')
    async with userside_api:
        try:
            old_device_id = await userside_api.device.get_device_id(
                object_type='switch', data_typer='ip',
                data_value=entry.ip_address.exploded)
        except RuntimeError:
            old_switch_present = False
            progresser.update_done('Свича с таким IP в Usersid\'e не нашлось')
        else:
            old_switch_present = True
            progresser.update_done('Нашли свич с таким IP в Usersid\'е')

        if old_switch_present:
            old_switch_data = await userside_api.device.get_data(
                object_type='switch', object_id=old_device_id,
                is_hide_ifaces_data=1)
            old_switch_data = old_switch_data[str(old_device_id)]
            # Запомнить коммутацию со старого свича
            await progresser.send_step('Запоминаем коммутацию старого свича')
            old_switch_commutation = await userside_api.commutation.get_data(
                object_type='switch', object_id=old_device_id)
            progresser.update_done('Запомнили коммутацию старого свича')

            # Переместить старый свич на сотрудника
            await progresser.send_step('Перемещаем старый свич на сотрудника')
            await transfer_inventory_to_employee(
                inventory_id=old_switch_data['inventory_id'],
                employee_id=entry.employee_id,
                userside_api=userside_api)
            progresser.update_done('Переместили старый свич на сотрудника')

        # Поставить новый свич в ящик
        await progresser.send_step('Ставим новый свич в ящик')
        mew_switch_inventory = await get_inventory_item(entry.serial_number,
                                                        userside_api)
        await transfer_inventory_to_node(mew_switch_inventory['id'],
                                         entry.node_id,
                                         entry.employee_id,
                                         userside_api)
        progresser.update_done('Поставили новый свич в ящик')

        # Исправить айпишник и количество портов
        await progresser.send_step('Устанавливаем IP и количество портов')
        new_device_id = await userside_api.device.get_device_id(
            object_type='switch',
            data_typer='serial_number',
            data_value=entry.serial_number
        )
        await userside_api.device.set_data(object_type='switch',
                                           object_id=new_device_id,
                                           param='ip',
                                           value=entry.ip_address.exploded)
        async with sessionmaker() as session:
            statement = select(Model).where(Model.id == entry.model_id)
            response = await session.execute(statement)
            model = response.scalars().first()
        await userside_api.device.set_data(object_type='switch',
                                           object_id=new_device_id,
                                           param='iface_count',
                                           value=model.portcount)
        progresser.update_done('Установили IP адрес и количество портов')

        if old_switch_present:
            # Восстановить коммутацию
            await progresser.send_step('Восстанавливаем аплинки/даунлинки')
            await update_up_down_link(
                old_uplink=old_switch_data['uplink_iface'],
                old_downlinks=old_switch_data['dnlink_iface'],
                movements=entry.port_movements,
                device_id=new_device_id,
                userside_api=userside_api)
            progresser.update_done('Восстановили аплинки/даунлинки')

            await progresser.send_step('Восстанавливаем коммутацию')
            await update_commutation(old_commutation=old_switch_commutation,
                                     movements=entry.port_movements,
                                     device_id=new_device_id,
                                     userside_api=userside_api)
            progresser.update_done('Восстановили коммутацию')

    await progresser.finish('Готово')
    await progresser.shutdown()
