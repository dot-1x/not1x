import asyncio
import re
from datetime import datetime

import aiohttp
from bs4 import BeautifulSoup as bs

from logs import setlog

_logger = setlog(__name__)

MAPSOURCE = {
    "zeddys": "http://sgfastdl.streamline-servers.com/fastdl/Zeddy/maps/",
    "gfl": "https://fastdl.gflclan.com/csgo/maps/",
}


async def aupdatemap():
    starttime = datetime.now()
    founded_maps = []
    async with aiohttp.ClientSession() as session:
        for src in MAPSOURCE.values():
            async with session.request("get", src) as req:
                site = bs(await req.read(), "html.parser")
                zemap = site.find_all(name="a", href=re.compile("ze_"))
                for _map in zemap:
                    if re.search("/ze_", _map["href"]):
                        _map = _map["href"].split("/")[-1]
                    else:
                        _map = _map["href"]
                    if re.search("bsp", _map) and re.search("bz2", _map):
                        _mapname = _map.split(".")[0]
                        founded_maps.append(_mapname.lower())

    map_set = list(dict.fromkeys(sorted(founded_maps)))
    map_str = "\n".join(map_set)
    with open("map_list/maplist.txt", "w+") as m:
        m.write(map_str)


def updatemap():
    # _loop = asyncio.get_event_loop()
    asyncio.run(aupdatemap())
    # starttime = datetime.now()
    # founded_maps = []
    # for src in MAPSOURCE.values():
    #     with requests.request("get", src) as req:
    #         site = bs(req.content, "html.parser")
    #         zemap = site.find_all(name="a", href=re.compile("ze_"))
    #         for _map in zemap:
    #             if re.search("/ze_", _map["href"]):
    #                 _map = _map["href"].split("/")[-1]
    #             else:
    #                 _map = _map["href"]
    #             if re.search("bsp", _map) and re.search("bz2", _map):
    #                 _mapname = _map.split(".")[0]
    #                 founded_maps.append(_mapname.lower())

    # map_set = list(dict.fromkeys(sorted(founded_maps)))
    # map_str = "\n".join(map_set)
    # with open("map_list/maplist.txt", "w+") as m:
    #     m.write(map_str)
    # endtime = datetime.now()
    # return endtime-starttime
