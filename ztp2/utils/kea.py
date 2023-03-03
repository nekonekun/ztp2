"""
This module is full of magic
KEA DHCP server is third-party software
We don't pay for KEA custom hooks and use free version
So we have to prepare values to match KEA format by ourselves
"""
import ipaddress
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models.kea_dhcp import Host, DHCPOption


def subnet_id(ip_address: ipaddress.IPv4Address) -> int:
    if ip_address in ipaddress.IPv4Network('172.22.0.0/16'):
        return 1
    elif ip_address in ipaddress.IPv4Network('10.10.0.0/16'):
        return 2
    elif ip_address in ipaddress.IPv4Network('10.0.0.0/16'):
        return 3
    raise


def hexstring_to_bytea(hexstring: str) -> bytes:
    answer = [int(hexstring[i:i + 2], 16) for i in range(0, len(hexstring), 2)]
    return bytes(answer)


def generate_option_125(firmware_filename: str):
    dlink_id = '000000AB'
    suboption_length = hex(1 + 1 + len(firmware_filename))[2:].upper().zfill(2)
    suboption_code = '01'
    filename_length = hex(len(firmware_filename))[2:].upper().zfill(2)
    hex_filename = ''.join([hex(ord(letter))[2:].upper().zfill(2)
                            for letter in firmware_filename])
    answer = dlink_id
    answer += suboption_length
    answer += suboption_code
    answer += filename_length
    answer += hex_filename
    return answer


def host_params(mac_address: str, ip_address: ipaddress.IPv4Address):
    return {
        'dhcp_identifier': hexstring_to_bytea(mac_address),
        'dhcp_identifier_type': 0,
        'dhcp4_subnet_id': subnet_id(ip_address),
        'ipv4_address': int(ip_address),
    }


def option_params_gen(host_id: int,
                      default_gateway: ipaddress.IPv4Interface,
                      cfg_tftp_server: str,
                      cfg_filename: str,
                      fw_tftp_server: str,
                      fw_filename: str):
    base = {
        'space': 'dhcp4',
        'host_id': host_id,
        'scope_id': 3,
        'persistent': False,
    }

    # option1: subnet mask
    option1 = bytes(str(int(default_gateway.netmask)), 'utf-8')
    specification1 = {
        'code': 1,
        'value': option1
    }
    yield base | specification1

    # option3: default gateway
    option3 = hex(int(default_gateway.ip))[2:].zfill(8)
    option3 = hexstring_to_bytea(option3)
    specification3 = {
        'code': 3,
        'value': option3
    }
    yield base | specification3

    # option66: configurations tftp server address
    option66 = bytes(cfg_tftp_server, 'utf-8')
    specification66 = {
        'code': 66,
        'value': option66
    }
    yield base | specification66

    # option67: configuration filename
    option67 = bytes(cfg_filename, 'utf-8')
    specification67 = {
        'code': 67,
        'value': option67
    }
    yield base | specification67

    # option125: firmware filename
    option125 = generate_option_125(fw_filename)
    option125 = hexstring_to_bytea(option125)
    specification125 = {
        'code': 125,
        'value': option125
    }
    yield base | specification125

    # option150: firmwares tftp server address
    option150 = int(ipaddress.IPv4Address(fw_tftp_server))
    option150 = hex(option150)[2:].zfill(8)
    option150 = hexstring_to_bytea(option150)
    specification150 = {
        'code': 150,
        'value': option150
    }
    yield base | specification150


async def create_host_and_options(db: AsyncSession,
                                  mac_address: str,
                                  ip_address: ipaddress.IPv4Address,
                                  default_gateway: ipaddress.IPv4Interface,
                                  cfg_tftp_server: str,
                                  cfg_filename: str,
                                  fw_tftp_server: str,
                                  fw_filename: str):
    host = Host(**host_params(mac_address, ip_address))  # noqa
    db.add(host)
    await db.flush()

    host_id = host.host_id
    for option_params in option_params_gen(host_id, default_gateway,
                                           cfg_tftp_server, cfg_filename,
                                           fw_tftp_server, fw_filename):
        option = DHCPOption(**option_params)  # noqa
        db.add(option)
    await db.commit()
