import ipaddress
import aiohttp


async def get_prefix_info(ip: str, session: aiohttp.ClientSession):
    async with session.get('/api/ipam/prefixes', params={'contains': ip}) \
            as response:
        possible_prefixes = await response.json()
    possible_prefixes = possible_prefixes['results']
    possible_prefixes.sort(
        key=lambda x: ipaddress.ip_network(x['prefix']).prefixlen,
        reverse=True,
    )
    prefix_info = possible_prefixes[0]
    return prefix_info


async def get_prefix(ip: str, session: aiohttp.ClientSession):
    prefix_info = await get_prefix_info(ip, session)
    prefix = prefix_info['prefix']
    return prefix


async def get_and_reserve_ip(prefix: str, session: aiohttp.ClientSession):
    async with session.get('/api/ipam/prefixes',
                           params={'prefix': prefix}) as response:
        prefix_info = await response.json()
    prefix_info = prefix_info['results'][0]
    vlan_info = prefix_info['vlan']
    async with session.get('/api/ipam/prefixes',
                           params={'vlan_id': vlan_info['id']}) as response:
        prefixes_in_vlan = await response.json()
    prefixes_in_vlan = prefixes_in_vlan['results']
    new_ip = None
    for prefix in prefixes_in_vlan:
        async with session.get(
                f'/api/ipam/prefixes/{prefix["id"]}/available-ips/'
        ) as response:
            answer = await response.json()
            if answer:
                new_ip = answer[0]['address']
                break
    await session.post('/api/ipam/ip-addresses/', json={'address': new_ip,
                                                        'status': 'reserved'})
    new_ip_address = ipaddress.IPv4Interface(new_ip).ip.exploded
    return new_ip_address


async def get_vlan(criteria: int | str,
                   session: aiohttp.ClientSession):
    if isinstance(criteria, int) or criteria.isdigit():
        async with session.get(f'/api/ipam/vlans/',
                               params={'vid': criteria}) as response:
            possible_vlans = await response.json()
        possible_vlans = possible_vlans['results']
        if len(possible_vlans) != 1:
            return int(criteria), f'v{str(criteria)}'
        target_vlan = possible_vlans[0]
        return str(target_vlan['vid']), target_vlan['name'].replace(' ', '')
    else:
        prefix_info = await get_prefix_info(criteria, session)
        vlan = prefix_info['vlan']
        return str(vlan['vid']), vlan['name'].replace(' ', '')


async def get_default_gateway(ip: str, session: aiohttp.ClientSession):
    prefix = await get_prefix(ip, session)
    async with session.get(f'/api/ipam/ip-addresses/',
                           params={'parent': prefix, 'tag': 'gw'}) as response:
        content = await response.json()
    possible_ips = content['results']
    if not possible_ips:
        raise
    if len(possible_ips) != 1:
        raise
    return ipaddress.IPv4Interface(possible_ips[0]['address'])


async def mark_ip_active(ip: str, session: aiohttp.ClientSession):
    async with session.get('/api/ipam/ip-addresses/',
                           params={'address': ip}) as response:
        content = await response.json()
    possible_ips = content['results']
    if not possible_ips:
        return
    if len(possible_ips) != 1:
        return
    netbox_id = possible_ips[0]['id']
    body = {'status': 'active'}
    await session.patch(f'/api/ipam/ip-addresses/{netbox_id}/', json=body)
