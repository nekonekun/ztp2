import aiohttp


class UsersideCategory:
    def __init__(self, category: str, api: 'UsersideAPI'):
        self._api = api
        self._cat = category

    def __getattr__(self, action: str):
        async def method(**kwargs):
            return await self._api._request(cat=self._cat,
                                            action=action,
                                            **kwargs)
        return method


class UsersideAPI:
    def __init__(self,
                 url: str,
                 key: str, ):
        self._url = url
        self._key = key
        self._in_use = 0
        self._session: aiohttp.ClientSession | None = None

    async def _request(self, cat: str, action: str, **kwargs):
        params = {'key': self._key, 'cat': cat, 'action': action}
        params.update(kwargs)
        async with self._session.get(url=self._url, params=params) as response:
            content = await response.json()
            if not response.ok:
                raise RuntimeError(
                    content.get('error', 'No error from Userside'))
            elif not response.content:
                raise RuntimeError(
                    'Empty response')
        return self._parse_response(content)

    @staticmethod
    def _parse_response(response: dict):
        if (id_ := response.get('id')) is not None:
            return id_
        if (data := response.get('data')) is not None:
            return data
        if (list_ := response.get('list')) is not None:
            return list_.split(',')
        return response

    def __getattr__(self, item):
        return UsersideCategory(item, self)

    async def __aenter__(self):
        if (self._in_use == 0) and (not self._session):
            self._session = aiohttp.ClientSession()
        self._in_use += 1
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self._in_use -= 1
        if (self._in_use == 0) and self._session:
            await self._session.close()
            self._session = None
