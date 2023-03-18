from scrapli import AsyncScrapli


async def extract_dlink_serial(session: AsyncScrapli):
    response = await session.send_command('show switch')
    serial_line = next(filter(lambda x: 'serial' in x.lower(),
                              response.result.split('\n')))
    serial_number = serial_line.split()[-1]
    return serial_number
