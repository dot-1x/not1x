import asyncio
import not1x
import numpy as np

from logs import setlog
from PIL import Image

_logger = setlog(__name__)


async def restart_map_loop(bot: not1x.Bot) -> None:
    loops = [l.get_name() for l in asyncio.all_tasks() if l.get_name() in bot.loop_maptsk]
    stopped_loop = [l for l in bot.loop_maptsk.keys() if l not in loops]
    for l in stopped_loop:
        try:
            bot.loop_maptsk[l].start()
            _logger.info(f"Successfully started loop: {l}")
        except Exception:
            _logger.warning(Exception)
