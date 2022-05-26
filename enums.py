from enum import Enum


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


if __name__ == "__main__":
    print(Data.STD_ERR_CHANNEL)
