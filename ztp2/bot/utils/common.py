import aiohttp
import ipaddress
import re
from typing import Any

MUST_STAY_KEYS = ['_msg', '_user', '_is_admin', '_owner', '_model']


def filter_data(data: dict[str, Any]):
    return {
        k: v for k, v in data.items()
        if (k in MUST_STAY_KEYS) or (k[0] != '_')
    }


def is_mac_address(mac: str) -> bool:
    two_symbols_regex = r'[0-9a-fA-F]{2}([-:.])' \
                        r'(?:[0-9a-fA-F]{2}\1){4}[0-9a-fA-F]{2}'
    four_symbols_regex = r'[0-9a-fA-F]{4}([-:.])[0-9a-fA-F]{4}\1[0-9a-fA-F]{4}'
    no_delimiters_regex = r'[0-9a-fA-F]{12}'
    if re.match(two_symbols_regex, mac) \
            or re.match(four_symbols_regex, mac) \
            or re.match(no_delimiters_regex, mac):
        return True
    else:
        return False


def is_ip_address(ip: str):
    try:
        ipaddress.IPv4Address(ip)
    except ipaddress.AddressValueError:
        return False
    else:
        return True


async def get_employee(criteria: int | str,
                       api_session: aiohttp.ClientSession):
    if criteria.isdigit():
        async with api_session.get(
                '/users/',
                params={'userside_id': criteria}) as response:
            employees = await response.json()
    else:
        async with api_session.get(
                '/users/',
                params={'name': criteria}) as response:
            employees = await response.json()
    if len(employees) != 1:
        return None
    return employees[0]
