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
