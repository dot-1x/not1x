import asyncio
import io
import typing as t

from pathlib import Path

import discord
import numpy as np
from PIL import Image

from logs import setlog

_logger = setlog(__name__)


class aiterator:
    def __init__(self, data=t.Union[list, tuple]) -> None:
        self.count = 0
        self.data = data

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.count >= len(self.data):
            raise StopAsyncIteration
        iter = self.data[self.count]
        self.count += 1
        return iter


async def most_color(asset: discord.Asset | None) -> discord.Colour:
    if not asset:
        return discord.Colour.from_rgb(245, 204, 22)

    img = Image.open(io.BytesIO(await asset.read()))
    img = img.convert("RGB")
    img = img.resize((150, 150))
    counter = 0
    r = g = b = 0
    for c in img.getdata():
        r += c[0]
        g += c[1]
        b += c[2]
        counter += 1

    return discord.Colour.from_rgb(round(r / counter), round(g / counter), round(b / counter))
