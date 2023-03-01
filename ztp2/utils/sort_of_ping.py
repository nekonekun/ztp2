import asyncio


TCP_ECHO_PORT = 7
TCP_TELNET_PORT = 23
TCP_HTTP_PORT = 80


async def check_port(ip_address: str, ports: list[int] | int = None):
    if not ports:
        ports = [TCP_ECHO_PORT, TCP_TELNET_PORT, TCP_HTTP_PORT]
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
