import asyncio
import re
import typing as t
from itertools import chain

import httpx
from bs4 import BeautifulSoup as bs

from logs import setlog

_logger = setlog(__name__)

MAPSOURCE = {
    "zeddys": "http://sgfastdl.streamline-servers.com/fastdl/Zeddy/maps/",
    "gfl": "https://fastdl.gflclan.com/csgo/maps/",
}


def parser(site: httpx.Response):
    scrap = bs(site.read(), "html.parser")
    maps = []
    for _map in scrap.find_all(name="a"):
        _map = _map["href"]
        if re.search("bsp", _map) and re.search("bz2", _map):
            if re.search("/", _map):
                _map = _map.split("/")[-1]
            _mapname: str = _map.split(".")[0]
            maps.append(_mapname.lower())
    return maps


async def updatemap():
    maps = []
    loop = asyncio.get_running_loop()
    async with httpx.AsyncClient() as client:
        for k in MAPSOURCE:
            resp = await client.get(MAPSOURCE[k])
            res = await loop.run_in_executor(None, parser, resp)
            maps.append(res)
    maps = sorted(list(dict.fromkeys(chain.from_iterable(maps)).keys()))
    with open("map_list/maplist.txt", "w+") as f:
        f.write("\n".join(maps))
