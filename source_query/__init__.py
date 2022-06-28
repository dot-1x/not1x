import asyncio
import ipaddress
import json

import a2s
import aiohttp
import discord
from a2s.info import SourceInfo
from bs4 import BeautifulSoup as bs

from logs import setlog

_logger = setlog("SourceQuery")


async def get_location(ip: str) -> dict | None:
    url = f"https://www.gametracker.com/server_info/{ip}"
    _res = {"flag": ":pirate_flag:", "location": "Unknown!"}
    async with aiohttp.ClientSession() as ses:
        async with ses.get(url) as req:
            if req.status != 200:
                return _res

            try:
                c = await req.text()
                _content = bs(c, "html.parser")
                _country = _content.find("span", attrs={"class": "blocknewheadercnt"})
                _image = _country.find("img")
            except:
                return _res
            with open("country.json", "r") as j:
                country = json.load(j)
                for k in country.keys():
                    if _image["title"].lower() in k.lower():
                        _res = {
                            "flag": f":flag_{country[k].lower()}:",
                            "location": _image["title"],
                        }
                        return _res
                return _res


class ServerInfo(discord.Embed):
    def __init__(self, ip: str, port: int, location: dict, server: SourceInfo, status: bool) -> None:

        self.ip_port = (str(ip), port)
        self.status = status

        _ip = ipaddress.ip_address(ip)
        _port = int(port)
        _loc = location
        _server = server

        fields = [
            (
                "Status : ",
                ":green_circle: Online!" if self.status else ":red_circle: Offline",
                True,
            ),
            ("Location : ", f"{_loc['flag']} {_loc['location']}", True),
            (
                "Quick Connect : ",
                f"steam://connect/{str(_ip)}:{_port}",
                False,
            ),
            ("Map : ", _server.map_name, True),
            ("Players : ", f"{_server.player_count}/{_server.max_players}", True),
        ]

        super().__init__(colour=discord.Colour.blurple(), title=_server.server_name, timestamp=discord.utils.utcnow())

        for (
            _name,
            _value,
            _inline,
        ) in fields:
            self.add_field(name=_name, value=_value, inline=_inline)

        self.__sv: SourceInfo = _server
        self.colour = discord.Colour.blurple()
        self.title = _server.server_name
        self.timestamp = discord.utils.utcnow()

    @property
    def name(self):
        return self.__sv.server_name

    @property
    def maps(self):
        return self.__sv.map_name

    @property
    def maxplayers(self):
        return self.__sv.max_players

    @property
    def player(self):
        return self.__sv.player_count

    async def players(self):
        try:
            return await a2s.aplayers((str(self.ip_port[0]), self.ip_port[1]), timeout=1)
        except Exception as e:
            _logger.warning(f"Failed to get {self.ip_port} player list\n" + str(e))
            return []


async def GetServer(ip: str, port: int):
    loc = await get_location(f"{str(ip)}:{port}")
    ip_port = (str(ip), port)
    try:
        _server: SourceInfo = await a2s.ainfo((str(ip), port), timeout=1)
    except:
        _server = SourceInfo()
        _server.map_name = "Unknown!"
        _server.player_count = 0
        _server.max_players = 0
        _server.server_name = f"{ip}:{port}"
        status = False
    else:
        status = True

    return ServerInfo(ip, port, loc, _server, status)
