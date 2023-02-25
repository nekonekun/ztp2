from collections import defaultdict
from ..remote_apis.snmp import DeviceSNMP


ETHERNET_IANA_IFTYPE = [
    6,  # ethernetCsmacd
    26,  # ethernet3Mbit
    62,  # fastEther
    69,  # fastEtherFX
    117  # gigabitEthernet
]


def bytes_to_portlist(snmp_response: bytes):
    # bytes to hex
    # b'\xdf\xa2y\xcb\xa7\xdc\xc0\x00' -> 'dfa279cba7dcc000'
    # b'\x03\xc0' -> '03c0
    hexed_response = map(lambda x: hex(x)[2:].zfill(2), snmp_response)
    hexed_response = ''.join(hexed_response)
    # hex to bin
    # '03c0' -> '0000001111000000'
    bined_response = map(lambda x: bin(int(x, 16))[2:].zfill(4), hexed_response)
    bined_response = ''.join(bined_response)
    # bin to portlist
    # '0000001111000000' -> [7, 8, 9, 10]
    return [index
            for index, value in enumerate(bined_response, 1)
            if value == '1']


def portlist_to_bytes(portlist: list[int], hexlen: int) -> bytes:
    # portlist to bin list
    #                             4
    # [4, 10] -> ['0', '0', '0', '1', '0', '0', '0', '0',
    #             '0', '1', '0', '0', '0', '0', '0', '0']
    #                   10
    resultlist = ['1' if i in portlist else '0'
                  for i in range(1, hexlen * 4 + 1)]
    # bin list to bin
    # ['0', '0', '0', '1', '0', '0', '0', '0',
    #  '0', '1', '0', '0', '0', '0', '0', '0'] -> '0001000001000000'
    resultlist = ''.join(resultlist)
    # bin to bin chunks (length of 8)
    # '0001000001000000' -> ['00010000', '01000000']
    resultlist = list(resultlist[8*x:8*(x+1)] for x in range(hexlen // 2))
    # bin chunks to bytes chunks (length of 1)
    # ['00010000', '01000000'] -> [b'\x10', b'@']
    resultlist = [int(chunk, 2).to_bytes(1, 'big') for chunk in resultlist]
    # bytes chunks to bytes
    return b''.join(resultlist)


async def get_vlan_list(ip_address: str, snmp: DeviceSNMP):
    async with snmp(ip_address=ip_address) as session:
        response = await session.walk('1.3.6.1.2.1.17.7.1.4.3.1.1')
    answer = {}
    for element in response:
        vlan_id = element.oid.split('.')[-1]
        vlan_name = element.value.decode('utf-8')
        answer[vlan_id] = vlan_name
    return answer


async def get_ports_descriptions(ip_address: str, snmp: DeviceSNMP):
    async with snmp(ip_address=ip_address) as session:
        response = await session.walk('1.3.6.1.2.1.2.2.1.3')
    interface_types = {}
    for element in response:
        interface_index = element.oid.split('.')[-1]
        interface_type = element.value
        interface_types[interface_index] = interface_type
    ethernet_interfaces = [if_index
                           for if_index, if_type in interface_types.items()
                           if if_type in ETHERNET_IANA_IFTYPE]
    async with snmp(ip_address=ip_address) as session:
        response = await session.walk('1.3.6.1.2.1.31.1.1.1.18')
    descriptions = {}
    for element in response:
        interface_index = element.oid.split('.')[-1]
        interface_description = element.value.decode('utf-8')
        if interface_index in ethernet_interfaces:
            descriptions[interface_index] = interface_description
    return descriptions


async def get_port_vlans(ip_address: str, snmp: DeviceSNMP):
    result = defaultdict(lambda: {'untagged': [], 'tagged': []})
    async with snmp(ip_address=ip_address) as session:
        all_ports = await session.walk('1.3.6.1.2.1.17.7.1.4.3.1.2')
    all_ports = {elem.oid.split('.')[-1]: bytes_to_portlist(elem.value)
                 for elem in all_ports}
    async with snmp(ip_address=ip_address) as session:
        untag_ports = await session.walk('1.3.6.1.2.1.17.7.1.4.3.1.4')
    untag_ports = {elem.oid.split('.')[-1]: bytes_to_portlist(elem.value)
                   for elem in untag_ports}
    for vlan, port_list in all_ports.items():
        for port in port_list:
            if port not in untag_ports[vlan]:
                result[str(port)]['tagged'].append(vlan)
    for vlan, port_list in untag_ports.items():
        for port in port_list:
            result[str(port)]['untagged'].append(vlan)
    return result
