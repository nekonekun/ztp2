import logging
import re
from copy import deepcopy
import aiogram.types
import aiohttp
import ipaddress
from typing import Any
from ...remote_apis.userside import UsersideAPI


def make_selecting_switch_message(response: list,
                                  current_user: dict[str, str | int],
                                  show_current_user: bool = True):
    if show_current_user:
        text = f'Свичи сотрудника {current_user["name"]}\n\n'
    else:
        text = f'Свичи всех сотрудников\n\n'
    response.sort(key=lambda x: x['id'])
    switches = ''
    for entry in response:
        done = ' ☒' if entry["status"] == 'DONE' else ''
        switches += f'{entry["id"]}. {entry["ip_address"]}{done}\n'
    if not switches:
        text += 'Нет свичей, подходящих под условия поиска\n'
    else:
        text += switches
    text += '\nВведи номер или IP-адрес нужного свича'
    return text


def is_ip_address(text: str):
    try:
        ip = ipaddress.ip_address(text)
    except ValueError:
        return False
    return True


def make_main_manage_message(entry: dict[str, Any]):
    text = f'Свич {entry["id"]}\n'
    text += f'Находится у сотрудника {entry["_owner"]["name"]}\n'
    text += f'Модель {entry["_model"]}\n'
    text += f'Серийный номер: {entry["serial_number"]}\n'
    text += f'IP адрес: {entry["ip_address"]}\n'
    text += f'MAC адрес: {entry["mac_address"]}\n'
    parent_switch = entry['parent_switch'] or '?'
    parent_port = entry['parent_port'] or '?'
    text += f'Подключен от {parent_switch} : {parent_port}\n'
    return text


def make_configuration_message(entry: dict[str, Any]):
    text = f'Свич {entry["id"]}\n'
    text += f'IP адрес: {entry["ip_address"]}\n\n'
    vlan_settings = entry['modified_vlan_settings']
    port_settings = entry['modified_port_settings']
    for vlan_id, vlan_name in vlan_settings.items():
        text += f'{vlan_id}: {vlan_name}\n'
    text += '\n'
    for index, settings in port_settings.items():
        if settings['tagged']:
            line = f'<b>{index} '
        else:
            line = f'{index} '
        if settings['description']:
            line += settings['description']
        line += ';'
        if settings['untagged']:
            line += ', '.join([str(vlan)+'u' for vlan in settings['untagged']])
            line += ';'
        if settings['tagged']:
            line += ', '.join([str(vlan)+'t' for vlan in settings['tagged']])
            line += '</b>'
        line += '\n'
        text += line
    return text


async def get_switch_list(api_session: aiohttp.ClientSession,
                          employee_id: int = None,
                          status: str = None,
                          limit: int = 10):
    params = {'limit': limit}
    if employee_id:
        params['employee_id'] = employee_id
    if status:
        params['status'] = status
    async with api_session.get('/entries/',
                               params=params) as response:
        content = await response.json()
    return content


async def start_ztp(api_session: aiohttp.ClientSession,
                    ztp_id: int,
                    sender_chat_id: int,
                    *additional_chat_ids: int):
    body = {'name': 'ztp2_main',
            'args': [ztp_id, sender_chat_id, *additional_chat_ids],
            'kwargs': {}}
    async with api_session.post('/celery/', json=body) as response:
        content = await response.json()
    return content['task_id']


async def ztp_finalize(api_session: aiohttp.ClientSession,
                       ztp_id: int,
                       sender_chat_id: int):
    body = {'name': 'ztp2_finalize',
            'args': [ztp_id, sender_chat_id],
            'kwargs': {}}
    async with api_session.post('/celery/', json=body) as response:
        content = await response.json()
    return content['task_id']


async def stop_ztp(api_session: aiohttp.ClientSession,
                   celery_id: str):
    await api_session.delete(f'/celery/{celery_id}/')


async def make_switch_data(msg: aiogram.types.Message,
                           user: dict[str, Any],
                           is_admin: bool,
                           entry: dict[str, Any],
                           api_session: aiohttp.ClientSession):
    data = {'_msg': msg,
            '_user': user,
            '_is_admin': is_admin}
    data.update(entry)
    async with api_session.get(f'/models/{entry["model_id"]}/') as response:
        content = await response.json()
    model = content['model']
    data['_model'] = model
    async with api_session.get(
            '/users/',
            params={'userside_id': entry['employee_id']}) as response:
        content = await response.json()
    data['_owner'] = content[0]
    return data


def extract_movements(text: str):
    port_movement_regex = re.compile(r'(\d+)[^0-9]+(\d+)')
    lines = text.split('\n')
    movements = {}
    for line in lines:
        match = port_movement_regex.match(line)
        if not match:
            return
        port_from, port_to = match.groups()
        if port_from in movements:
            return
        movements[port_from] = port_to
    return movements


def apply_movements(original_settings: dict, movements: dict):
    modified_settings = deepcopy(original_settings)
    for from_, to_ in movements.items():
        modified_settings[to_] = original_settings[from_]
        if from_ not in movements.values():
            modified_settings[from_] = {
                    'tagged': [],
                    'untagged': [],
                    'description': ''
                }
    return modified_settings


def extract_names(text: str):
    names_regex = re.compile(r'^(\d+)(?:\s+([\w:_\-,.]+))?$')
    lines = text.split('\n')
    names = {}
    for line in lines:
        match = names_regex.match(line)
        if not match:
            return
        index, name = match.groups()
        names[index] = name
    return names


def expand_ranges(ranges: str):
    ranges_regex = re.compile(r'(?:\d+-\d+|\d+)(?:,(?:\d+-\d+|\d+))*')
    if not ranges_regex.match(ranges):
        logging.error('wrong ports format')
        return
    result = []
    for elem in ranges.split(','):
        if '-' in elem:
            start, stop = map(int, elem.split('-'))
            result.extend(range(start, stop + 1))
        else:
            result.append(elem)
    return list(map(str, result))


def update_port_vlan_settings(original_settings: dict,
                              action: str,
                              vlanids: list,
                              ports: list):
    action, mode = action.split('_')
    vlanids = list(map(int, vlanids))
    for port in ports:
        untag = original_settings[port]['untagged']
        tag = original_settings[port]['tagged']
        if action == 'delete':
            untag = [vlan for vlan in untag if vlan not in vlanids]
            tag = [vlan for vlan in tag if vlan not in vlanids]
        elif mode == 'untagged':
            untag.extend(vlanids)
            untag.sort(key=lambda x: int(x))
            tag = [vlan for vlan in tag if vlan not in vlanids]
        else:
            tag.extend(vlanids)
            tag.sort(key=lambda x: int(x))
            untag = [vlan for vlan in untag if vlan not in vlanids]
        original_settings[port]['untagged'] = sorted(list(set(untag)))
        original_settings[port]['tagged'] = sorted(list(set(tag)))
    return original_settings
