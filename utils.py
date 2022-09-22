import io
import secrets
import traceback
import typing as t
from datetime import datetime
from pathlib import Path

import discord
import numpy as np
import pandas as pd
from discord.ext import commands
from PIL import Image

from enums import *
from logs import setlog

_logger = setlog(__name__)
help_command = {}


async def most_color(asset: discord.Asset | None) -> discord.Colour:
    if not asset:
        return discord.Colour.from_rgb(245, 204, 22)

    with Image.open(io.BytesIO(await asset.read())) as i:
        i = i.convert("RGB")
        color_size = len(i.getdata())
        r = round(sum([_r for _r in i.getdata(0)]) / color_size)
        g = round(sum([_r for _r in i.getdata(1)]) / color_size)
        b = round(sum([_r for _r in i.getdata(2)]) / color_size)
        return discord.Colour.from_rgb(r, g, b)


def dominant_color(file: str | bytes):
    with Image.open(file) as i:
        i = i.convert("RGB")
        color_size = len(i.getdata())
        r = round(sum([_r for _r in i.getdata(0)]) / color_size)
        g = round(sum([_r for _r in i.getdata(1)]) / color_size)
        b = round(sum([_r for _r in i.getdata(2)]) / color_size)
        return (r, g, b)


def log_exception(exc: Exception, typ: ExcType, id: int = 0):
    if not id:
        id = secrets.randbits(64)
    _tb = Path(typ).exists()
    _mode = "x" if not _tb else "a"
    with open(typ, _mode) as f:
        f.write(
            str(datetime.utcnow())
            + "\n"
            + f"ID: {id}\n"
            + "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
            + "\n"
        )


def parse_history(history: t.List[server_info]):
    data: t.Dict[str, ServerHistory] = {}
    for s in history:
        if s.map not in data:
            data[s.map] = {
                "Map": s.map,
                "Play_Time": s.playtime,
                "Played": s.played,
                "Average_Player": [s.average_players],
                "Last_Played": s.lastplayed,
            }
        else:
            if data[s.map]["Last_Played"] < s.lastplayed:
                data[s.map]["Last_Played"] = s.lastplayed
            data[s.map]["Play_Time"] += s.playtime
            data[s.map]["Played"] += s.played
            data[s.map]["Average_Player"].append(s.average_players)
    for k in data:
        total = np.average(data[k]["Average_Player"])
        data[k]["Average_Player"]: float = round(total, 2)
        yield ServerHistory(**data[k])


def addhelp(help):
    def decorator(func: t.Callable):
        if func in help_command:
            raise ValueError(f"{func} has already help description")
        help_command[func] = help
        return func

    return decorator


def generate_help_embed(command: t.Union[discord.SlashCommand, discord.SlashCommandGroup]) -> discord.SlashCommand:
    if isinstance(command, discord.SlashCommandGroup):
        return [generate_help_embed(c) for c in command.subcommands]
    else:
        return command
