import json

from db import connection
from not1x import Bot

CONFIG = None
with open("_debugs/config.json", "r") as cfg:
    CONFIG = json.load(cfg)
    CONFIG["path"] = cfg.name

if __name__ == "__main__":
    db = connection()
    bot = Bot(CONFIG, token=CONFIG["token"], db=db)
    bot.run()
