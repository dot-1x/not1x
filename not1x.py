import asyncio
import os
import pathlib
import traceback
import typing as t
from ast import Store
from datetime import datetime
from ipaddress import IPv4Address, ip_address

import discord
from discord.ext import bridge, commands, tasks
from discord.ext.commands.errors import *

import ui_utils
from command_error import CheckError, StdErrChannel
from db import connection
from enums import *
from logs import setlog
from tasks.map_task import ServerTask

__version__ = "0.6r1.2"

_logger = setlog(__name__)


class CustomHelp(commands.HelpCommand):
    def __init__(self, **options):
        super().__init__(**options)

    async def send_bot_help(self, mapping: t.Mapping[t.Optional[commands.Cog], t.List[commands.Command]]):
        _logger.debug(mapping)
        await self.context.send(content="A help command passed!")


class Bot(bridge.Bot):
    def __init__(self, config: dict, *, token: str, db: connection):
        self.prefix = "."
        self.ready = False
        self.help = CustomHelp()
        self.config = config
        self.__token = token
        intent = discord.Intents(guilds=True, members=True, messages=True, presences=True)

        super().__init__(
            command_prefix=self.prefix,
            owner_ids=Data.OWNER.value,
            case_insensitive=True,
            intents=intent,
            help_command=self.help,
        )
        _logger.info("++++++ Loading not1x ++++++")
        _logger.info(f"Version: {__version__}")

        self._pl_list_button = False
        self._persiew: t.Dict[str, ui_utils.PlayerListV] = {}
        self.server_task: t.Dict[str, tasks.Loop] = {}

        self.load_extension_from("cogs")
        # self.load_extension("utils")
        self.add_bridge_command(self.reload_ext)
        self.db = db
        self.data = {}

    def run(self):
        super().run(token=self.__token)

    async def close(self):
        _logger.critical("Bot Closed!")

        return await super().close()

    async def map_tasks(self):
        _sv_list: t.List[str] = self.config["serverquery"]
        for _sv in _sv_list:
            if not ":" in _sv:
                _logger.warning('Missing delimiter ":" on ' + _sv)
                continue
            try:
                ip_address(_sv.split(":")[0])
            except Exception as e:
                _logger.warning(str(e) + " on " + _sv)
                continue
            if not self._pl_list_button:
                _view = ui_utils.PlayerListV(self, _sv.split(":")[0], _sv.split(":")[1])
                self.persview[_sv] = _view
                self.add_view(_view)
            sv = ServerTask(self, _sv, _sv, self.persview[_sv])
            self.server_task[_sv] = tasks.Loop(
                sv.servercheck,
                60,
                discord.MISSING,
                discord.MISSING,
                time=discord.MISSING,
                count=None,
                loop=self.loop,
                reconnect=True,
            )
        for task in self.server_task:
            self.server_task[task].start()
            self.server_task[task].get_task().set_name(task)

        self._pl_list_button = True
        _logger.info("loop map task has been started!")

    @property
    def persview(self):
        return self._persiew

    @persview.setter
    def persview(self, key: str, val: str):
        if key in self._persiew:
            raise ValueError(f"key: {key} is already on persistent view")
        self._persiew[key] = val

    ####################### Bot's event handler #######################
    async def on_ready(self):

        if self.ready:
            _logger.info(f"Bot reconnected as: {self.user}")
            return

        self.ready = True

        async for guild in self.fetch_guilds():
            try:
                await self.db.loadguild(guild.id)
            except Exception as e:
                _logger.critical("Failed to load guild from database")
                self.loop.stop()

        await self.map_tasks()

        for c in self.cogs:
            _logger.info(f"Loaded cog: {c}")

        _logger.info(f"++++++ Successfully Logged in as: {self.user} ++++++")

    async def on_guild_join(self, guild: discord.Guild):
        try:
            await self.db.loadguild(guild.id)
        except:
            _logger.error("Failed to insert guild to database")

    async def on_error(self, event_method: str, *args: t.Any, **kwargs: t.Any) -> None:
        _logger.debug(event_method)
        _logger.debug(args)
        _logger.debug(kwargs)
        return await super().on_error(event_method, *args, **kwargs)

    async def on_application_command_error(self, ctx: discord.ApplicationContext, err: discord.DiscordException):
        await CheckError(ctx, err)

    async def on_command_error(self, ctx: commands.Context, err: commands.CommandError):
        await CheckError(ctx, err)

    ####################### End of bot event handler #######################
    async def reload_extensions(self, name, *, package=None, ctx=commands.Context):
        try:
            super().reload_extension(name, package=package)
        except:
            return super().reload_extension(name, package=package)
        else:
            _logger.info(f"Reloaded extension {name}")
            await ctx.send(f"Reloaded extension {name}")

    def load_extension(self, name, *, package=None, store=False):
        super().load_extension(name, package=package, store=store)

    def load_extension_from(
        self,
        *paths: t.Union[str, pathlib.Path],
        recursive: bool = False,
        must_exist: bool = True,
    ):
        """
        load extension from a folder, forked from hikari-lightbulb
        """
        if len(paths) > 1 or not paths:
            for path_ in paths:
                self.load_extensions_from(path_, recursive=recursive, must_exist=must_exist)
            return

        path = paths[0]

        if isinstance(path, str):
            path = pathlib.Path(path)

        try:
            path = path.resolve().relative_to(pathlib.Path.cwd())
        except ValueError:
            raise ValueError(f"'{path}' must be relative to the working directory") from None

        if not path.is_dir():
            if must_exist:
                raise FileNotFoundError(f"'{path}' is not an existing directory")
            return

        glob = path.rglob if recursive else path.glob

        for ext_path in glob("[!_]*.py"):
            ext = str(ext_path.with_suffix("")).replace(os.sep, ".")
            self.load_extension(name=ext, store=False)

    def check_test(ctx: commands.Context):
        return ctx.channel.id == Data.TEST_CHANNEL.value

    @bridge.bridge_command(
        desciprtion="reload any extension",
        usage="( reload_ext ): ext name, empty for all loaded ext",
        guild_ids=[620983321677004800]
    )
    @discord.option(name="exts", type=str, description="extension name to reload", required=False)
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def reload_ext(ctx: bridge.BridgeContext, *, exts=None):
        await ctx.reply("Reloading extensions")
        if ctx.author.id not in ctx.bot.owner_ids:
            raise commands.NotOwner("You Do not have permission to use this commands")
        bot: Bot = ctx.bot
        if not exts:
            for k in list(bot.extensions):
                await bot.reload_extensions(k, ctx=ctx)
            return
        if len(exts) > 1:
            for ext_ in exts:
                await bot.reload_extensions(ext_, ctx=ctx)
        ext_ = exts[0]
        await bot.reload_extensions(ext_, ctx=ctx)
