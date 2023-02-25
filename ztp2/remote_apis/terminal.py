from scrapli.driver.core import AsyncIOSXEDriver


class DeviceTerminal:
    def __init__(self, username: str, password: str, enable: str):
        self.username = username
        self.password = password
        self.enable = enable

    def __call__(self, ip_address: str,
                 device_class: str,
                 **kwargs):
        if device_class == 'AsyncIOSXEDriver':
            return AsyncIOSXEDriver(
                host=ip_address,
                auth_username=self.username,
                auth_password=self.password,
                auth_secondary=self.enable,
                auth_strict_key=False,
                **kwargs
            )
        else:
            raise NotImplementedError
