import aioftp


async def get_file_content(filename: str,
                           client: aioftp.Client,
                           folder: str = None):
    file_content = ''
    if folder:
        filename = '/' + folder.strip('/') + '/' + filename
    async with client.download_stream(filename) as stream:
        async for block in stream.iter_by_block():
            file_content += block.decode('utf-8')
    return file_content


async def pattern_in_file_content(filename: str,
                                  pattern: str,
                                  client: aioftp.Client,
                                  folder: str = None):
    file_content = await get_file_content(filename, client, folder)
    return pattern in file_content