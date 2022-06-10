import asyncio
import aiohttp
import a2s
import ipaddress
import requests
import json

from bs4 import BeautifulSoup as bs
from a2s.info import SourceInfo


async def get_location(ip: str) -> dict | None:
    url = f"https://www.gametracker.com/server_info/{ip}"
    async with aiohttp.ClientSession() as ses:
        async with ses.get(url) as req:
            if req.status != 200:
                return None

            c = await req.text(encoding="utf-8")
            try:
                _content = bs(c, "html.parser")
                _country = _content.find("span", attrs={"class": "blocknewheadercnt"})
                _image = _country.find("img")
            except:
                return None

            with open("country.json", "r") as j:
                js = json.load(j)
                for k in js.keys():
                    if _image["title"].lower() in k.lower():
                        return {
                            "flag": f":flag_{js[k].lower()}:",
                            "location": _image["title"],
                        }
                j.close()
            req.close()
        await ses.close()


class CheckServer:
    def __init__(
        self,
        ip: ipaddress.ip_address,
        port: int,
        server: SourceInfo,
        *,
        status: bool = False,
        name: str = "Unknown",
        maps: str = "Unkown",
        players: int = 0,
        maxplayers: int = 0,
        location: str = "Unknown!",
        location_flag: str = ":pirate_flag:",
    ) -> None:
        self.ip = ipaddress.ip_address(ip)
        self.port = int(port)
        self.ip_port = (str(self.ip), self.port)
        self.server = server
        self.status = status
        self.name = name
        self.maps = maps
        self.players = players
        self.maxplayers = maxplayers
        self.location = location
        self.flag = location_flag

    @classmethod
    async def GetServer(cls, ip: ipaddress.ip_address, port: int):
        try:
            _server: SourceInfo = await a2s.ainfo((str(ip), port), timeout=1)
        except asyncio.exceptions.TimeoutError:
            _server = SourceInfo
            return cls(ip, port, _server, name=f"{str(ip)}:{port}")
        else:
            _location = await get_location(f"{str(ip)}:{port}")
            if not _location:
                _loc = "Unknown!"
                _flag = ":pirate_flag:"
            else:
                _loc = _location["location"]
                _flag = _location["flag"]
            return cls(
                ip,
                port,
                _server,
                status=True,
                name=_server.server_name,
                maps=_server.map_name,
                players=_server.player_count,
                maxplayers=_server.max_players,
                location=_loc,
                location_flag=_flag,
            )

    async def GetPlayers(self) -> None | list:
        try:
            self.player_list = await a2s.aplayers(self.ip_port, timeout=1)
        except asyncio.exceptions.TimeoutError:
            self.player_list = None

        return self.player_list
