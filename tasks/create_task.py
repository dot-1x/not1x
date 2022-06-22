import asyncio
import typing as t

import discord
from discord.ext import commands, tasks

from logs import setlog

_logger = setlog(__name__)


class CustomTask(tasks.Loop):
    def __init__(
        self,
        bot: commands.Bot,
        coro: None,
        seconds: float,
        /,
        name: str = "Custom",
        count: t.Optional[int | None] = None,
        reconnect: bool = True,
    ):
        self.bot = bot
        self.name = name

        super().__init__(
            coro=coro,
            seconds=seconds,
            hours=discord.MISSING,
            minutes=discord.MISSING,
            time=discord.MISSING,
            count=count,
            reconnect=reconnect,
            loop=discord.MISSING,
        )

    def start(self, *args: t.Any, **kwargs: t.Any) -> asyncio.Task[None]:
        return super().start(*args, **kwargs)

    def after_loop(self):
        _logger.info(f"Finished looping: {self.name}")
