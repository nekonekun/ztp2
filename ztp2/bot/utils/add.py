import logging
import re


def make_pre_mode_select_message(data: dict):
    if data['_user']:
        text = f'Добавляем свич для сотрудника {data["_user"]["name"]}\n\n'
    else:
        text = f'Укажи имя или номер сотрудника'
        return text
    if serial_number := data['serial_number']:
        text += f'Серийный номер: {serial_number}\n'
    else:
        text += 'Надо указать серийный номер.\n'
        return text
    if mac_address := data['mac_address']:
        text += f'MAC адрес: {mac_address}\n'
    elif serial_number:
        text += 'Надо указать MAC адрес.\n'
        return text
    if data['_duplicate']:
        text += '\nСвич с таким серийником или маком уже был добавлен. ' \
                'Просто предупреждаю\n'
    text += '\nВыбери тип установки'
    return text


def make_mode_select_message(data: dict):
    text = f'Добавляем свич для сотрудника {data["_user"]["name"]}\n\n'
    text += f'Серийный номер: {data["serial_number"]}\n'
    text += f'MAC адрес: {data["mac_address"]}\n'
    mode = data['mode']
    if mode == 'change_switch':
        text += 'Тип: замена свича\n\n'
        text += 'Укажи IP свича, который будешь менять'
    elif mode == 'new_switch':
        text += 'Тип: установка дополнительного свича\n\n'
        text += 'Укажи IP и порт свича, от которого будет подключен ' \
                'дополнительный свич в формате [ip] [port]'
    elif mode == 'new_house':
        text += 'Тип: запуск нового дома\n\n'
        text += 'Укажи номер заявки на Пуско-наладку'
    return text


def make_confirmation_text(data: dict):
    text = f'Добавляем свич для сотрудника {data["_user"]["name"]}\n\n'
    text += f'Серийный номер: {data["serial_number"]}\n'
    text += f'MAC адрес: {data["mac_address"]}\n'
    mode = data['mode']
    logging.error(mode)
    if mode == 'change_switch':
        text += 'Тип: замена свича\n'
        text += f'IP-адрес свича под замену: {data["ip_address"]}\n'
    elif mode == 'new_switch':
        text += 'Тип: установка дополнительного свича\n'
        text += f'Вышестоящий свич: {data["ip_address"]}\n'
        text += f'Порт на вышестоящем свиче: {data["port"]}\n'
    text += f'Адрес ящика: {data["node_name"]}'
    return text


def is_mac_address(mac: str) -> bool:
    two_symbols_regex = r'[0-9a-fA-F]{2}([-:.])' \
                        r'(?:[0-9a-fA-F]{2}\1){4}[0-9a-fA-F]{2}'
    four_symbols_regex = r'[0-9a-fA-F]{4}([-:.])[0-9a-fA-F]{4}\1[0-9a-fA-F]{4}'
    if re.match(two_symbols_regex, mac) or re.match(four_symbols_regex, mac):
        return True
    else:
        return False
