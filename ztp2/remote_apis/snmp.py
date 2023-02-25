import aiosnmp


class DeviceSNMP:
    def __init__(self, community: str):
        self.community = community

    def __call__(self, ip_address: str,
                 port: int = 161,
                 timeout: float = 1.0,
                 retries: int = 2):
        return aiosnmp.Snmp(host=ip_address,
                            port=port,
                            community=self.community,
                            timeout=timeout,
                            retries=retries)
