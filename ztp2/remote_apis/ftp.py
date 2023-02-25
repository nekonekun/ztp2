import aioftp


class ContextedFTP:
    def __init__(self, host: str, username: str, password: str):
        self.host = host
        self.username = username
        self.password = password
        self.client: aioftp.Client | None = None

    async def __aenter__(self):
        self.client = aioftp.Client()
        await self.client.connect(self.host)
        await self.client.login(self.username, self.password)
        return self.client

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.quit()
        self.client = None


class FtpFactory:
    def __init__(self, host: str, username: str, password: str):
        self.host = host
        self.username = username
        self.password = password

    def __call__(self):
        return ContextedFTP(self.host, self.username, self.password)
