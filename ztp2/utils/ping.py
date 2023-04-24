import aioping


async def check(ip_address: str, timeout: int = 2):
    try:
        await aioping.ping(ip_address, timeout=timeout)
        return True
    except TimeoutError:
        return False
