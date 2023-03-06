from netmiko.linux import LinuxSSH


class ServerTerminalFactory:
    def __init__(self, username: str, password: str, ip_address: str):
        self.username = username
        self.password = password
        self.ip_address = ip_address

    def __call__(self):
        return LinuxSSH(device_type='linux',
                        host=self.ip_address,
                        username=self.username,
                        password=self.password)
