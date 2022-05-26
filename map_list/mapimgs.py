import aiohttp
import asyncio
import re

from bs4 import BeautifulSoup as bs

loop = asyncio.get_event_loop()


async def con():
    _client: aiohttp.ClientSession = aiohttp.ClientSession()
    _req = await _client.get(url="https://vauff.com/mapimgs/")
    _web = bs(await _req.text(), "html.parser")
    zemap = _web.find_all("a", href=re.compile("^/mapimgs/ze_"))
    print(zemap)
    await _client.close()


loop.run_until_complete(con())
# print(_web.content)
