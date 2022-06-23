import json

from not1x import Bot

CONFIG = None
with open("_debugs/config.json", "r") as cfg:
    CONFIG = json.load(cfg)
    CONFIG["path"] = cfg.name

if __name__ == "__main__":
    bot = Bot(CONFIG, token=CONFIG["devtoken"])
    bot.run()
