import asyncio
from pathlib import Path

import discord
import numpy as np
from PIL import Image

from logs import setlog

_logger = setlog(__name__)


async def most_color(asset: discord.Asset | None) -> discord.Colour:
    if not asset:
        return discord.Colour((245, 204, 22))

    img = Image.open(await asset.read())
    img = img.convert("RGB")
    img = img.resize((150, 150))
    counter = 0
    r = g = b = 0
    for c in img.getdata():
        r += c[0]
        g += c[1]
        b += c[2]
        counter += 1

    return discord.Colour((round(r / counter), round(g / counter), round(b / counter)))
