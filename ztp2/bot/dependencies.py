import aiohttp


class ApiSessionFactory:
    def __init__(self, *,
                 unix_socket: str | None = None,
                 base_url: str | None = None):
        self.unix_socket = unix_socket
        self.base_url = base_url

    def __call__(self, *args, **kwargs):
        if self.unix_socket:
            return aiohttp.ClientSession(
                connector=aiohttp.UnixConnector(path=self.unix_socket)
            )
        else:
            return aiohttp.ClientSession(base_url=self.base_url)
