import asyncio
import io
import typing as t
from datetime import datetime

import discord
import numpy as np
import pandas as pd
from PIL import Image

from enums import *
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


def parse_history(history: t.List[t.Tuple[int, str, str, datetime, datetime, int, int, float]]):
    data: t.Dict[str, ServerHistory] = {}
    for _, ip, Maps, TimePlayed, LastPlayed, PlayTime, Played, AveragePlayers in history:
        if Maps not in data:
            data[Maps] = {
                "Map": Maps,
                "Play_Time": PlayTime,
                "Played": Played,
                "Average_Player": [AveragePlayers],
                "Last_Played": LastPlayed,
            }
        else:
            if data[Maps]["Last_Played"] < LastPlayed:
                data[Maps]["Last_Played"] = LastPlayed
            data[Maps]["Play_Time"] += PlayTime
            data[Maps]["Played"] += Played
            data[Maps]["Average_Player"].append(AveragePlayers)
    for k in data:
        total = np.average(data[k]["Average_Player"])
        data[k]["Average_Player"]: int = total
        yield ServerHistory(**data[k])
