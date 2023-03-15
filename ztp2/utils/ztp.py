import logging
from abc import ABC, abstractmethod
import aioftp
import aiohttp
import aiosnmp
from jinja2 import Template
from scrapli.driver.core import AsyncIOSXEDriver

from ..remote_apis.snmp import DeviceSNMP
from .snmp import get_port_vlans, bytes_to_portlist, portlist_to_bytes
from ..db.models.ztp import Model, Entry
from .netbox import get_vlan, get_default_gateway
from .ftp import get_file_content, upload_file


class BaseInterface(ABC):
    @abstractmethod
    def __init__(self, ip: str, interface: str, management_vlan: int):
        raise NotImplementedError

    @abstractmethod
    async def switch_to_management(self):
        raise NotImplementedError

    @abstractmethod
    async def switch_back(self):
        raise NotImplementedError

    @abstractmethod
    async def get_untagged(self):
        raise NotImplementedError


class CiscoInterface(BaseInterface):
    def __init__(self, ip: str,
                 interface: str,
                 management_vlan: int,
                 terminal: AsyncIOSXEDriver):
        self.ip: str = ip
        self.interface: str = interface
        self.management_vlan = str(management_vlan)
        self.untagged: str | None = None
        self.terminal: AsyncIOSXEDriver | None = terminal

    async def get_untagged(self):
        resp = await self.terminal.send_command(
            f'show run int {self.interface}'
        )
        native = list(
            filter(lambda x: x.startswith('switchport trunk native vlan'),
                   map(str.strip, resp.result.split('\n'))))
        if native:
            self.untagged = native[0].split(' ')[-1]
            return self.untagged

    async def switch_to_management(self):
        commands = [
            f'interface {self.interface}',
            f'switchport trunk native vlan {self.management_vlan}'
        ]
        await self.terminal.send_configs(commands)

    async def switch_back(self):
        if self.untagged:
            commands = [
                f'interface {self.interface}',
                f'switchport trunk native vlan {self.untagged}'
            ]
        else:
            commands = [
                f'interface {self.interface}',
                f'no switchport trunk native vlan'
            ]
        await self.terminal.send_configs(commands)

    async def __aenter__(self):
        await self.terminal.open()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.terminal.close()


class DlinkInterface(BaseInterface):
    def __init__(self, ip: str,
                 interface: str,
                 management_vlan: int,
                 snmp_factory: DeviceSNMP):
        self.ip: str = ip
        self.interface: str = interface
        self.management_vlan: str = str(management_vlan)
        self.untagged: list | None = None
        self.snmp_factory: DeviceSNMP = snmp_factory
        self.snmp: aiosnmp.Snmp | None = None

    async def switch_to_management(self):
        if self.untagged:
            for vlan in self.untagged:
                # Remove interface from "untagged ports"
                resp = await self.snmp.get(f'1.3.6.1.2.1.17.7.1.4.3.1.4.{vlan}')
                hexlen = len(resp[0].value) * 2
                plist = bytes_to_portlist(resp[0].value)
                plist.remove(int(self.interface))
                await self.snmp.set([(f'1.3.6.1.2.1.17.7.1.4.3.1.4.{vlan}',
                                      portlist_to_bytes(plist, hexlen))])
                # Remove interface from "all ports"
                resp = await self.snmp.get(f'1.3.6.1.2.1.17.7.1.4.3.1.2.{vlan}')
                hexlen = len(resp[0].value) * 2
                plist = bytes_to_portlist(resp[0].value)
                plist.remove(int(self.interface))
                await self.snmp.set([(f'1.3.6.1.2.1.17.7.1.4.3.1.2.{vlan}',
                                      portlist_to_bytes(plist, hexlen))])
        # Add interface to management "all ports"
        resp = await self.snmp.get(
            f'1.3.6.1.2.1.17.7.1.4.3.1.2.{self.management_vlan}')
        hexlen = len(resp[0].value) * 2
        plist = bytes_to_portlist(resp[0].value)
        plist = list(set(plist) | {int(self.interface)})
        await self.snmp.set(
            [(f'1.3.6.1.2.1.17.7.1.4.3.1.2.{self.management_vlan}',
              portlist_to_bytes(plist, hexlen))])
        # Add interface to management "untagged ports"
        resp = await self.snmp.get(
            f'1.3.6.1.2.1.17.7.1.4.3.1.4.{self.management_vlan}')
        hexlen = len(resp[0].value) * 2
        plist = bytes_to_portlist(resp[0].value)
        plist = list(set(plist) | {int(self.interface)})
        await self.snmp.set(
            [(f'1.3.6.1.2.1.17.7.1.4.3.1.4.{self.management_vlan}',
              portlist_to_bytes(plist, hexlen))])

    async def switch_back(self):
        # Remove interface from management "untagged ports"
        resp = await self.snmp.get(
                f'1.3.6.1.2.1.17.7.1.4.3.1.4.{self.management_vlan}')
        hexlen = len(resp[0].value) * 2
        plist = bytes_to_portlist(resp[0].value)
        plist.remove(int(self.interface))
        await self.snmp.set(
            [(f'1.3.6.1.2.1.17.7.1.4.3.1.4.{self.management_vlan}',
              portlist_to_bytes(plist, hexlen))])
        # Add interface to management "all ports" just to be sure
        resp = await self.snmp.get(
                f'1.3.6.1.2.1.17.7.1.4.3.1.2.{self.management_vlan}')
        hexlen = len(resp[0].value) * 2
        plist = bytes_to_portlist(resp[0].value)
        plist = list(set(plist) | {int(self.interface)})
        await self.snmp.set(
            [(f'1.3.6.1.2.1.17.7.1.4.3.1.2.{self.management_vlan}',
              portlist_to_bytes(plist, hexlen))])
        if self.untagged:
            for vlan in self.untagged:
                # Add interface to "all ports"
                resp = await self.snmp.get(
                    f'1.3.6.1.2.1.17.7.1.4.3.1.2.{vlan}')
                hexlen = len(resp[0].value) * 2
                plist = bytes_to_portlist(resp[0].value)
                plist = list(set(plist) | {int(self.interface)})
                await self.snmp.set([(f'1.3.6.1.2.1.17.7.1.4.3.1.2.{vlan}',
                                      portlist_to_bytes(plist, hexlen))])
                # Add interface to "untagged ports"
                resp = await self.snmp.get(
                    f'1.3.6.1.2.1.17.7.1.4.3.1.4.{vlan}')
                hexlen = len(resp[0].value) * 2
                plist = bytes_to_portlist(resp[0].value)
                plist = list(set(plist) | {int(self.interface)})
                await self.snmp.set([(f'1.3.6.1.2.1.17.7.1.4.3.1.4.{vlan}',
                                      portlist_to_bytes(plist, hexlen))])

    async def get_untagged(self):
        port_vlans = await get_port_vlans(self.ip, self.snmp_factory)
        untagged = port_vlans[self.interface]['untagged']
        if untagged:
            self.untagged = untagged
            return self.untagged

    async def __aenter__(self):
        self.snmp = self.snmp_factory(self.ip)
        await self.snmp.__aenter__()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.snmp.__aexit__(exc_type, exc_val, exc_tb)
        self.snmp = None


def make_config_from_template(template: str, **kwargs):
    template = Template(template)
    config = template.render(**kwargs)
    return config


async def gather_initial_configuration_parameters(
        entry: Entry, model: Model, netbox: aiohttp.ClientSession):
    vlan_id, vlan_name = await get_vlan(entry.ip_address, netbox)
    default_gateway = await get_default_gateway(entry.ip_address, netbox)
    return {
        'configuration_prefix': model.configuration_prefix,
        'portcount': model.portcount,
        'ip_address': entry.ip_address,
        'management_vlan_id': vlan_id,
        'management_vlan_name': vlan_name,
        'subnet_mask': default_gateway.netmask.exploded,
        'gateway': default_gateway.ip.exploded,
    }


async def generate_initial_config(entry: Entry, model: Model,
                                  base_folder: str,
                                  template_filename: str,
                                  config_filename: str,
                                  netbox: aiohttp.ClientSession,
                                  ftp: aioftp.Client):
    config_filename = base_folder + config_filename
    template_filename = base_folder + template_filename
    template = await get_file_content(template_filename, ftp)
    params = await gather_initial_configuration_parameters(entry, model, netbox)
    config = make_config_from_template(template, **params)
    await upload_file(config_filename, config, ftp)


async def gather_full_configuration_parameters(
        entry: Entry, model: Model, netbox: aiohttp.ClientSession):
    vlan_id, vlan_name = await get_vlan(entry.ip_address, netbox)
    return {
        'portcount': model.portcount,
        'management_vlan_tag': vlan_id,
        'port_settings': entry.modified_port_settings,
        'vlan_settings': entry.modified_vlan_settings,
        'ip_address': entry.ip_address.exploded
    }


async def generate_full_config(entry: Entry, model: Model,
                               base_folder: str,
                               template_filename: str,
                               config_filename: str,
                               netbox: aiohttp.ClientSession,
                               ftp: aioftp.Client):
    config_filename = base_folder + config_filename
    template_filename = base_folder + template_filename
    template = await get_file_content(template_filename, ftp)
    params = await gather_full_configuration_parameters(entry, model, netbox)
    config = make_config_from_template(template, **params)
    await upload_file(config_filename, config, ftp)
