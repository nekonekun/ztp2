import logging
from abc import ABC, abstractmethod
import aiosnmp
from scrapli.driver.core import AsyncIOSXEDriver

from ..remote_apis.snmp import DeviceSNMP
from .snmp import get_port_vlans, bytes_to_portlist, portlist_to_bytes


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
                hexlen = len(resp[0].value)
                plist = bytes_to_portlist(resp[0].value)
                plist.remove(int(self.interface))
                await self.snmp.set([(f'1.3.6.1.2.1.17.7.1.4.3.1.4.{vlan}',
                                      portlist_to_bytes(plist, hexlen))])
                # Remove interface from "all ports"
                resp = await self.snmp.get(f'1.3.6.1.2.1.17.7.1.4.3.1.2.{vlan}')
                hexlen = len(resp[0].value)
                plist = bytes_to_portlist(resp[0].value)
                plist.remove(int(self.interface))
                await self.snmp.set([(f'1.3.6.1.2.1.17.7.1.4.3.1.2.{vlan}',
                                      portlist_to_bytes(plist, hexlen))])
        # Add interface to management "all ports"
        resp = await self.snmp.get(
            f'1.3.6.1.2.1.17.7.1.4.3.1.2.{self.management_vlan}')
        hexlen = len(resp[0].value)
        plist = bytes_to_portlist(resp[0].value)
        plist = list(set(plist) | {int(self.interface)})
        await self.snmp.set(
            [(f'1.3.6.1.2.1.17.7.1.4.3.1.2.{self.management_vlan}',
              portlist_to_bytes(plist, hexlen))])
        # Add interface to management "untagged ports"
        resp = await self.snmp.get(
            f'1.3.6.1.2.1.17.7.1.4.3.1.4.{self.management_vlan}')
        hexlen = len(resp[0].value)
        plist = bytes_to_portlist(resp[0].value)
        plist = list(set(plist) | {int(self.interface)})
        await self.snmp.set(
            [(f'1.3.6.1.2.1.17.7.1.4.3.1.4.{self.management_vlan}',
              portlist_to_bytes(plist, hexlen))])

    async def switch_back(self):
        # Remove interface from management "untagged ports"
        resp = await self.snmp.get(
                f'1.3.6.1.2.1.17.7.1.4.3.1.4.{self.management_vlan}')
        hexlen = len(resp[0].value)
        plist = bytes_to_portlist(resp[0].value)
        plist.remove(int(self.interface))
        await self.snmp.set(
            [(f'1.3.6.1.2.1.17.7.1.4.3.1.4.{self.management_vlan}',
              portlist_to_bytes(plist, hexlen))])
        # Add interface to management "all ports" just to be sure
        resp = await self.snmp.get(
                f'1.3.6.1.2.1.17.7.1.4.3.1.2.{self.management_vlan}')
        hexlen = len(resp[0].value)
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
                hexlen = len(resp[0].value)
                plist = bytes_to_portlist(resp[0].value)
                plist = list(set(plist) | {int(self.interface)})
                await self.snmp.set([(f'1.3.6.1.2.1.17.7.1.4.3.1.2.{vlan}',
                                      portlist_to_bytes(plist, hexlen))])
                # Add interface to "untagged ports"
                resp = await self.snmp.get(
                    f'1.3.6.1.2.1.17.7.1.4.3.1.4.{vlan}')
                hexlen = len(resp[0].value)
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
