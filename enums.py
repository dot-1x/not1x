from dataclasses import dataclass
import typing as t
from datetime import datetime
from enum import Enum

import discord

UknownMap = t.NewType("UnkownMap", str)
ExcType = t.NewType("ExcType", str)

cmd_err = ExcType("logs/cmderror.log")
base_err = ExcType("logs/traceback.log")


class Status(Enum):
    OFFLINE = ":red_circle: Offline!"
    ONLINE = ":green_circle: Online!"


class Data(Enum):
    PREFIX = "."
    OWNER = [732842920889286687]
    TEST_CHANNEL = 885845218144948264
    STD_ERR_CHANNEL = 966627932875415572
    MAP_TRACKING = 886032874917199913
    GUILDS = [751758928395763712, 620983321677004800]
    OWNER_GUILD = 620983321677004800
    TASK_INTERVAL = 60


class MapEnum(Enum):
    UNKOWN = UknownMap


class ServerHistory(t.TypedDict):
    Map: str
    Play_Time: int
    Played: int
    Average_Player: t.Optional[int | t.List[int]]
    Last_Played: datetime


class ExceptionType(Enum):
    CMD = cmd_err
    BASE = base_err


class CommandHelp(t.TypedDict):
    name: str
    desctiption: str
    parent: str | None
    option: t.List[discord.Option]


class server_info(t.NamedTuple):
    id: int
    tracking_ip: str
    map: str
    date: datetime
    lastplayed: datetime
    playtime: int
    played: int
    average_players: int


class user_data(t.NamedTuple):
    id: int
    userid: int
    name: str
    notified_maps: str
