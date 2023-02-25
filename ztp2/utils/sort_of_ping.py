import asyncio


async def check_port(ip_address: str, ports: list[int] | int = None):
    if not ports:
        ports = [23, 80, 22]
    elif isinstance(ports, int):
        ports = [ports]
    for port in ports:
        try:
            await asyncio.wait_for(
                asyncio.open_connection(ip_address, port),
                timeout=1
            )
            return True
        except asyncio.TimeoutError:
            continue
        except ConnectionRefusedError:
            return True
    return False
