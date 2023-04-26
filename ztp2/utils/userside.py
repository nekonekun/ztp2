from enum import Enum
import re

from ..remote_apis.userside import UsersideAPI


class InventoryStorage(Enum):
    Supplier = '101'
    Warehouse = '204'
    Subscriber = '205'
    Node = '206'
    CableLine = '210'
    Task = '212'
    Building = '213'
    Employee = '215'
    Decommissioned = '900'


class SubAccount(Enum):
    SubreportLong = '01'
    SubreportShort = '02'
    Supplies = '03'
    Rent = '08'
    SoldAccounting = '09'


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
        match = re.search(r'(\d+\.\d+\.\d+\.\d+/\d+)', chunk)
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
    vlan_ids = re.findall(r'\[(\d+)]', specification)
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


async def transfer_inventory_to_employee(inventory_id: int,
                                         employee_id: int,
                                         userside_api: UsersideAPI):
    dst_account = InventoryStorage.Employee.value \
                  + SubAccount.Supplies.value \
                  + str(employee_id).zfill(7)
    await userside_api.inventory.transfer_inventory(inventory_id=inventory_id,
                                                    dst_account=dst_account,
                                                    employee_id=employee_id)


async def transfer_inventory_to_node(inventory_id: int,
                                     node_id: int,
                                     employee_id: int,
                                     userside_api: UsersideAPI):
    dst_account = InventoryStorage.Node.value \
                  + SubAccount.Supplies.value \
                  + str(node_id).zfill(7)
    await userside_api.inventory.transfer_inventory(inventory_id=inventory_id,
                                                    dst_account=dst_account,
                                                    employee_id=employee_id)


async def update_up_down_link(old_uplink: str,
                              old_downlinks: str,
                              movements: dict,
                              device_id: int,
                              userside_api: UsersideAPI):
    uplinks = old_uplink.split(',')
    uplinks = [movements.get(u, u) for u in uplinks]
    uplinks = ','.join(uplinks)
    downlinks = old_downlinks.split(',')
    downlinks = [movements.get(u, u) for u in downlinks]
    downlinks = ','.join(downlinks)
    await userside_api.device.set_data(object_type='switch',
                                       object_id=device_id,
                                       param='downlink_port',
                                       value=downlinks)
    await userside_api.device.set_data(object_type='switch',
                                       object_id=device_id,
                                       param='uplink_port',
                                       value=uplinks)


async def update_commutation(old_commutation: dict,
                             movements: dict,
                             device_id: int,
                             userside_api: UsersideAPI):
    for port_index, commutation_data in old_commutation.items():
        for neighbor in commutation_data:
            if neighbor['object_type'] in ['fiber', 'cross']:
                await userside_api.commutation.add(
                    object_type='switch',
                    object_id=device_id,
                    object1_port=movements.get(port_index, port_index),
                    object2_type=neighbor['object_type'],
                    object2_id=neighbor['object_id'],
                    object2_side=neighbor['direction'],
                    object2_port=neighbor['interface'],
                )
            else:
                await userside_api.commutation.add(
                    object_type=neighbor['object_type'],
                    object_id=neighbor['object_id'],
                    object1_port=neighbor['interface'],
                    object2_type='switch',
                    object2_id=device_id,
                    object2_port=movements.get(port_index, port_index)
                )


async def get_node_name(node_id: int, userside_api: UsersideAPI):
    nodes_data = await userside_api.node.get(id=node_id)
    node_data = nodes_data[str(node_id)]
    node_name = node_data['name']
    return node_name
