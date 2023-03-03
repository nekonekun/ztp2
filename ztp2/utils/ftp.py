import aioftp
import io


async def get_file_content(filename: str,
                           client: aioftp.Client):
    file_content = ''
    async with client.download_stream(filename) as stream:
        async for block in stream.iter_by_block():
            file_content += block.decode('utf-8')
    return file_content


async def pattern_in_file_content(filename: str,
                                  pattern: str,
                                  client: aioftp.Client):
    file_content = await get_file_content(filename, client)
    return pattern in file_content


async def upload_file(filename: str,
                      content: str,
                      client: aioftp.Client):
    async with client.upload_stream(filename) as stream:
        await stream.write(content.encode())
