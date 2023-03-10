import aiohttp
import ipaddress
from typing import Any


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


def make_main_manage_message(entry: dict[str, Any],
                             user: dict[str, Any]):
    text = f'Свич {entry["id"]}\n'
    text += f'Находится у сотрудника {user["name"]}\n'
    text += f'IP адрес: {entry["ip_address"]}\n'
    text += f'Серийный номер: {entry["serial_number"]}\n'
    text += f'MAC адрес: {entry["mac_address"]}\n'
    parent_switch = entry['parent_switch'] or '?'
    parent_port = entry['parent_port'] or '?'
    text += f'Подключен от {parent_switch} : {parent_port}\n'
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


async def stop_ztp(api_session: aiohttp.ClientSession,
                   celery_id: str):
    await api_session.delete(f'/celery/{celery_id}/')
