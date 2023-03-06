import pprint
import re

from ztp2.remote_apis.userside import UsersideAPI


async def get_device_model(serial_number: str, userside_api: UsersideAPI):
    inventory_id = await userside_api.inventory.get_inventory_id(
        data_typer='serial_number',
        data_value=serial_number)
    inventory_data = await userside_api.inventory.get_inventory(
        id=inventory_id)
    model = inventory_data['name']
    return model


async def get_node_id(ip_address: str, userside_api: UsersideAPI):
    device_id = await userside_api.device.get_device_id(object_type='switch',
                                                        data_typer='ip',
                                                        data_value=ip_address)
    device_data = await userside_api.device.get_data(object_type='switch',
                                                     object_id=device_id)
    device_data = device_data[str(device_id)]
    node_id = device_data['node_id']
    return node_id


async def get_task_prefixes(task_id: int, userside_api: UsersideAPI):
    task_data = await userside_api.task.show(id=task_id)
    additional_data = task_data['additional_data']
    target_field = additional_data['266']
    specification = target_field['value']
    management_prefix = None
    other_prefixes = []
    for chunk in specification.split(';'):
        match = re.match(r'\d+\.\d+\.\d+\.\d+/\d+', chunk)
        if not match:
            continue
        prefix = match.group(1)
        if 'mgmt' in chunk:
            management_prefix = prefix
        else:
            other_prefixes.append(prefix)
    return [management_prefix] + other_prefixes


async def get_task_vlans(task_id: int, userside_api: UsersideAPI):
    task_data = await userside_api.task.show(id=task_id)
    additional_data = task_data['additional_data']
    target_field = additional_data['266']
    specification = target_field['value']
    vlan_ids = re.findall(r'\[\d+]', specification)
    return vlan_ids


async def get_parent_switch_port(ip_address: str, userside_api: UsersideAPI):
    device_id = await userside_api.device.get_device_id(object_type='switch',
                                                        data_typer='ip',
                                                        data_value=ip_address)
    devices_data = await userside_api.device.get_data(object_type='switch',
                                                      object_id=device_id,
                                                      is_hide_ifaces_data=1)
    device_data = devices_data[str(device_id)]
    uplink = device_data['uplink_iface'].split(',')
    if len(uplink) != 1:
        return None, None
    uplink = uplink[0]
    commutation = await userside_api.commutation.get_data(object_type='switch',
                                                          object_id=device_id,
                                                          is_finish_data='1')
    if uplink not in commutation:
        return None, None
    uplink_neighbor = commutation[uplink]['finish']
    if uplink_neighbor['object_type'] != 'switch':
        return None, None
    parent_port = str(uplink_neighbor['interface'])
    parent_switch_id = str(uplink_neighbor['object_id'])
    parent_switch_data = await userside_api.device.get_data(
        object_type='switch',
        object_id=parent_switch_id,
        is_hide_ifaces_data=1
    )
    parent_switch_data = parent_switch_data[parent_switch_id]
    parent_switch = parent_switch_data['host']
    return parent_switch, parent_port


async def get_inventory_item(serial_number: str, userside_api: UsersideAPI):
    inv_id = await userside_api.inventory.get_inventory_id(
        data_typer='serial_number',
        data_value=serial_number
    )
    inv_data = await userside_api.inventory.get_inventory(id=inv_id)
    return inv_data
