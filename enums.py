import typing as t
from enum import Enum
from datetime import datetime

UknownMap = t.NewType("UnkownMap", str)


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
    Ip: str
    Map: str
    Play_Time: int
    Played: int
    Average_Player: t.List[int]
    Last_Played: datetime