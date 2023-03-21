import aiosnmp.exceptions
from fastapi import APIRouter, Depends
import ipaddress
import logging


from .. import crud
from ... import utils
from ..schemas.entries import Entry, EntryCreateRequest, EntryPatchRequest
from ..stub import ztp_db_session_stub, userside_api_stub, snmp_ro_stub, \
    netbox_session_stub, celery_stub, kea_db_session_stub, ftp_settings_stub, \
    contexted_ftp_stub


entries_router = APIRouter()


@entries_router.post('/', response_model=Entry | None)
async def entries_create(req: EntryCreateRequest,
                         db=Depends(ztp_db_session_stub),
                         kea=Depends(kea_db_session_stub),
                         userside_api=Depends(userside_api_stub),
                         snmp_ro=Depends(snmp_ro_stub),
                         netbox=Depends(netbox_session_stub),
                         celery=Depends(celery_stub),
                         ftp_settings=Depends(ftp_settings_stub),
                         ftp=Depends(contexted_ftp_stub)):
    mount_type = req.mount_type

    # Common parameters
    new_object = {'serial_number': req.serial_number.upper(),
                  'status': 'WAITING', 'employee_id': req.employee_id,
                  'port_movements': {}}
    mac_address = [letter
                   for letter in req.mac_address.lower()
                   if letter in '0123456789abcdef']
    mac_address = ''.join(mac_address)
    new_object['mac_address'] = mac_address

    # Duplicate check
    possible_serial_duplicates = await crud.entry.read_by_clauses(
        db, serial_number=new_object['serial_number']
    )
    possible_mac_duplicates = await crud.entry.read_by_clauses(
        db, mac_address=new_object['mac_address']
    )
    if mount_type == 'changeSwitch':
        possible_ip_duplicates = await crud.entry.read_by_clauses(
            db, ip_address=req.ip_address
        )

    # Task ID
    if mount_type == 'newHouse':
        new_object['task_id'] = req.task_id
    else:
        new_object['task_id'] = None

    # Node ID
    if mount_type == 'newHouse':
        new_object['task_id'] = req.node_id
    else:
        new_object['node_id'] = await utils.get_node_id(req.ip_address.exploded,
                                                        userside_api)
    # IP address
    if mount_type == 'changeSwitch':
        new_object['ip_address'] = req.ip_address.exploded
    else:
        if mount_type == 'newSwitch':
            management_prefix = await utils.get_prefix(req.ip_address.exploded,
                                                       netbox)
        else:
            task_prefixes = await utils.get_task_prefixes(
                new_object['task_id'], userside_api
            )
            management_prefix = task_prefixes[0]
        new_ip = await utils.get_and_reserve_ip(management_prefix, netbox)
        new_object['ip_address'] = new_ip

    # Parent switch and port
    if mount_type == 'newSwitch':
        new_object['parent_switch'] = req.ip_address.exploded  # noqa
        new_object['parent_port'] = req.parent_port
        new_object['autochange_vlans'] = True
    elif mount_type == 'newHouse':
        new_object['parent_switch'] = None
        new_object['parent_port'] = None
        new_object['autochange_vlans'] = False
    elif mount_type == 'changeSwitch':
        switch, port = await utils.userside.get_parent_switch_port(
            new_object['ip_address'], userside_api
        )
        new_object['parent_switch'] = switch
        new_object['parent_port'] = port
        if (switch is not None) and (port is not None):
            new_object['autochange_vlans'] = True
        else:
            new_object['autochange_vlans'] = False

    mgmt_id, mgmt_name = await utils.netbox.get_vlan(new_object['ip_address'],
                                                     netbox)
    # VLAN settings
    vlan_settings = {'1': 'default',
                     mgmt_id: mgmt_name}
    if mount_type == 'newHouse':
        task_prefixes = await utils.get_task_prefixes(
            new_object['task_id'], userside_api
        )
        if task_prefixes:
            for prefix in task_prefixes:
                vlan_id, vlan_name = await utils.netbox.get_vlan(prefix, netbox)
                vlan_settings[vlan_id] = vlan_name
        task_vlans = await utils.userside.get_task_vlans(req.task_id, netbox)
        if task_vlans:
            for vlan in task_vlans:
                vlan_id, vlan_name = await utils.netbox.get_vlan(vlan, netbox)
                if vlan_id not in vlan_settings:
                    vlan_settings[vlan_id] = vlan_name
    else:
        try:
            vlans = await utils.snmp.get_vlan_list(req.ip_address.exploded,
                                                   snmp_ro)
            for vlan_id, vlan_name in vlans.items():
                vlan_settings[vlan_id] = vlan_name
        except aiosnmp.exceptions.SnmpTimeoutError:
            logging.error('Timeout while reading old switch vlans')
    new_object['vlan_settings'] = vlan_settings.copy()
    new_object['modified_vlan_settings'] = vlan_settings.copy()

    # Model ID
    model = await utils.get_device_model(new_object['serial_number'],
                                         userside_api)
    model_obj = await crud.model.read_by_model(db, model)
    if model_obj:
        model_obj = model_obj[0]
    new_object['model_id'] = model_obj.id

    # Port settings
    portcount = model_obj.portcount
    if mount_type == 'changeSwitch':
        port_settings = {
            str(port): {'description': '',
                        'tagged': [],
                        'untagged': []}
            for port in range(1, portcount + 1)
        }
        try:
            descriptions = await utils.snmp.get_ports_descriptions(
                req.ip_address.exploded, snmp_ro)
        except aiosnmp.exceptions.SnmpTimeoutError:
            logging.error('Timeout while reading old switch descriptions')
        else:
            for index, description in descriptions.items():
                if index in port_settings:
                    port_settings[index]['description'] = description
                else:
                    port_settings[index] = {'description': description,
                                            'tagged': [],
                                            'untagged': []}
        try:
            port_vlans = await utils.snmp.get_port_vlans(req.ip_address.exploded,
                                                         snmp_ro)
        except aiosnmp.exceptions.SnmpTimeoutError:
            logging.error('Timeout while reading old switch vlans')
        else:
            for index, port_vlan in port_vlans.items():
                if index in port_settings:
                    port_settings[index].update(port_vlan)
                else:
                    port_settings[index] = {'description': '',
                                            **port_vlan}
    else:
        port_settings = {
            str(port): {'description': '',
                        'tagged': [int(mgmt_id)],
                        'untagged': [1]}
            for port in range(1, portcount + 1)
        }
    new_object['original_port_settings'] = port_settings.copy()
    new_object['modified_port_settings'] = port_settings.copy()

    answer = await crud.entry.create(db, obj_in=new_object)

    default_gateway = await utils.netbox.get_default_gateway(
        answer.ip_address.exploded, netbox)

    initial_config_filepath = f'{ftp_settings.configs_initial_path}' \
                              f'{answer.ip_address.exploded}.cfg'
    firmware_filepath = ftp_settings.firmwares_path + model_obj.firmware

    await utils.kea.create_host_and_options(
        kea, answer.mac_address, answer.ip_address, default_gateway,
        ftp_settings.host, initial_config_filepath, ftp_settings.host,
        firmware_filepath)

    initial_template_filepath = f'{ftp_settings.templates_initial_path}' \
                                f'{model_obj.default_initial_config}'
    full_config_filepath = f'{ftp_settings.configs_full_path}' \
                           f'{answer.ip_address.exploded}.cfg'
    full_template_filepath = f'{ftp_settings.templates_full_path}' \
                             f'{model_obj.default_full_config}'
    async with ftp as ftp_instance:
        await utils.ztp.generate_initial_config(
            answer, model_obj, ftp_settings.tftp_folder,
            initial_template_filepath, initial_config_filepath, netbox,
            ftp_instance)
        await utils.ztp.generate_full_config(
            answer, model_obj, ftp_settings.tftp_folder,
            full_template_filepath, full_config_filepath, netbox, ftp_instance)

    celery_task_kwargs = {
        'entry_id': answer.id,
        'mac_address': answer.mac_address,
        'ftp_host': ftp_settings.host,
        'config_filename': initial_config_filepath,
        'firmware_filename': firmware_filepath
     }
    celery.send_task('ztp2_office_dhcp', kwargs=celery_task_kwargs)

    return answer


@entries_router.get('/', response_model=list[Entry])
async def entries_list(skip: int = 0,
                       limit: int = 100,
                       employee_id: int = None,
                       status: str = None,
                       ip_address: ipaddress.IPv4Address = None,
                       mac_address: str = None,
                       serial_number: str = None,
                       db=Depends(ztp_db_session_stub)):
    entries = await crud.entry.read_by_clauses(db, employee_id=employee_id,
                                               status=status,
                                               ip_address=ip_address,
                                               mac_address=mac_address,
                                               serial_number=serial_number,
                                               skip=skip, limit=limit)
    return entries


@entries_router.get('/{entry_id}/', response_model=Entry | None)
async def entries_read(entry_id: int, db=Depends(ztp_db_session_stub)):
    entry = await crud.entry.read(db=db, id=entry_id)
    return entry


@entries_router.patch('/{entry_id}/', response_model=Entry)
async def entries_partial_update(entry_id: int, req: EntryPatchRequest,
                                 db=Depends(ztp_db_session_stub),
                                 userside_api=Depends(userside_api_stub),
                                 kea=Depends(kea_db_session_stub),
                                 celery=Depends(celery_stub),
                                 ftp_settings=Depends(ftp_settings_stub),
                                 ftp=Depends(contexted_ftp_stub),
                                 netbox=Depends(netbox_session_stub)):
    entry: Entry = await crud.entry.read(db=db, id=entry_id)
    update_obj = EntryPatchRequest()
    # Employee changed check
    if entry.employee_id != req.employee_id:
        # Update ZTP DB entry
        update_obj.employee_id = req.employee_id
        # If ZTP is not finished -- move switch to new employee
        if not entry.finished_at:
            async with userside_api:
                inv_item = await utils.userside.get_inventory_item(
                    entry.serial_number, userside_api)
                await utils.userside.transfer_inventory_to_employee(
                    inv_item['id'], req.employee_id, userside_api)
    # IP address changed check
    if entry.ip_address != req.ip_address:
        # Update ZTP DB entry
        update_obj.ip_address = req.ip_address
        # Update KEA DHCP entry
        old_clean_mac = ''.join(letter
                                for letter in entry.mac_address.lower()
                                if letter in '0123456789abcdef')
        initial_config_filepath = f'{ftp_settings.configs_initial_path}' \
                                  f'{req.ip_address.exploded}.cfg'
        await utils.kea_change_ip_address(kea,
                                          old_clean_mac,
                                          req.ip_address.exploded,
                                          initial_config_filepath)
        # Update office DHCP entry
        celery_task_kwargs = {
            'entry_id': entry_id,
            'field': 'ip_address',
            'value': req.ip_address.exploded,
        }
        celery.send_task('ztp2_office_dhcp_edit', kwargs=celery_task_kwargs)
        # Generate new initial config
        model_obj = await crud.model.read(db, entry.model_id)
        initial_template_filepath = f'{ftp_settings.templates_initial_path}' \
                                    f'{model_obj.default_initial_config}'
        async with ftp as ftp_instance:
            await utils.ztp.generate_initial_config(
                entry, model_obj, ftp_settings.tftp_folder,
                initial_template_filepath, initial_config_filepath, netbox,
                ftp_instance)
    # MAC address changed check
    new_clean_mac = ''.join(letter
                            for letter in req.mac_address.lower()
                            if letter in '0123456789abcdef')
    old_clean_mac = ''.join(letter
                            for letter in entry.mac_address.lower()
                            if letter in '0123456789abcdef')
    if old_clean_mac != new_clean_mac:
        # Update ZTP DB entry
        update_obj.mac_address = req.mac_address
        # Update KEA DHCP entry
        await utils.kea.kea_change_mac_address(kea,
                                               old_clean_mac,
                                               new_clean_mac)
        # Update Office DHCP entry
        celery_task_kwargs = {
            'entry_id': entry_id,
            'field': 'mac_address',
            'value': new_clean_mac,
        }
        celery.send_task('ztp2_office_dhcp_edit', kwargs=celery_task_kwargs)
    # Port settings changed check
    ports_changed = entry.modified_port_settings != req.modified_port_settings
    vlans_changed = entry.modified_vlan_settings != req.modified_vlan_settings
    moves_changed = entry.port_movements != req.port_movements
    if ports_changed or vlans_changed or moves_changed:
        logging.error('FULL CONFIG REBUILD')
        update_obj.modified_port_settings = req.modified_port_settings
        update_obj.modified_vlan_settings = req.modified_vlan_settings
        update_obj.port_movements = req.port_movements
        model_obj = await crud.model.read(db, entry.model_id)
        full_config_filepath = f'{ftp_settings.configs_full_path}' \
                               f'{entry.ip_address.exploded}.cfg'
        full_template_filepath = f'{ftp_settings.templates_full_path}' \
                                 f'{model_obj.default_full_config}'
        logging.error(full_template_filepath)
        logging.error(full_config_filepath)
        async with ftp as ftp_instance:
            await utils.ztp.generate_full_config(
                req, model_obj, ftp_settings.tftp_folder,
                full_template_filepath, full_config_filepath, netbox,
                ftp_instance)
    if req.parent_port or req.parent_switch:
        update_obj.autochange_vlans = True
    if entry.parent_switch != req.parent_switch:
        update_obj.parent_switch = req.parent_switch
    if entry.parent_port != req.parent_port:
        update_obj.parent_port = req.parent_port

    answer = await crud.entry.update(db=db, db_obj=entry, obj_in=update_obj)
    return answer


@entries_router.delete('/{entry_id}/')
async def entries_delete(entry_id: int, db=Depends(ztp_db_session_stub)):
    answer = await crud.entry.delete(db, id=entry_id)
    return answer
