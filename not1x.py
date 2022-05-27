import asyncio
import pathlib
import typing as t
import os
import discord
import ui_utils

from db import loadguild, connection
from enums import *
from logs import setlog
from discord.ext import bridge, commands
from discord.ext.commands import HelpCommand
from discord.ext.commands.errors import *
from command_error import CheckError, std_err_channels
from tasks.map_task import ServerTask

__version__ = "0.3.2"
_logger = setlog(__name__)

class CustomHelp(HelpCommand):
    def __init__(self, **options):
        super().__init__(**options)

    async def send_bot_help(self, mapping: t.Mapping[t.Optional[commands.Cog], t.List[commands.Command]]):
        _logger.debug(mapping)
        await self.context.send(content="A help command passed!")

class Bot(bridge.Bot):
    def __init__(self):
        self.prefix = "."
        self.ready = False
        self.help = CustomHelp()
        super().__init__(
            command_prefix=self.prefix,
            owner_ids=Data.OWNER.value,
            case_insensitive=True,
            intents=discord.Intents.all(),
            help_command=self.help
        )

        _logger.info("++++++ Loading not1x ++++++")
        _logger.info(f"Version: {__version__}")

        self._pl_list_button = False
        self._persiew = {}

        self.load_extension_from("cogs")
        self.add_bridge_command(self.reload_ext)

    def run(self):
        try:
            loop = asyncio.get_event_loop()
            loop.run_until_complete(connection.conn())
        except:
            _logger.critical("Failed to connect to database")
            loop.run_until_complete(self.close())
            return
        with open("_debugs/dev.txt") as token:
            super().run(token.read().strip())

    def map_tasks(self):
        with open("source_query/serverlist.txt") as _sv_list:

            for _sv in _sv_list.read().split("\n"):
                if not self._pl_list_button:
                    _view = ui_utils.PlayerListV.generate_view(_sv.split(":")[0], _sv.split(":")[1])
                    self.persview[_sv] = _view
                    self.add_view(_view)

                loop = ServerTask(self, _sv, _sv, Data.TASK_INTERVAL.value, self.persview[_sv])
                loop.start()

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
            _logger.info(f"Reconnected as: {self.user}")
            return
        self.ready = True

        async for guild in self.fetch_guilds():
            await loadguild(guild.id)

        self.map_tasks()

        _logger.info(f"++++++ Successfully Logged in as: {self.user} ++++++")

    async def on_guild_join(self, guild: discord.Guild):
        await loadguild(guild.id)
        return super().on_guild_join(guild)

    async def on_message(self, message: discord.Message = None):
        try:
            if message.channel.id == Data.STD_ERR_CHANNEL.value and not message.author.bot:
                await message.delete()
                raise std_err_channels
        except std_err_channels:
            _logger.warning(std_err_channels)
            _logger.warning("Cannot send message in stderr channel")
            return
        return await super().on_message(message)

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

    def load_extension(self, name, *, package=None):
        super().load_extension(name, package=package)

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
            self.load_extension(name=ext)

    def check_test(ctx: commands.Context):
        return ctx.channel.id == Data.TEST_CHANNEL.value

    @bridge.bridge_command(
        desciprtion="reload any extension",
        usage="( reload_ext ): ext name, empty for all loaded ext",
    )
    @discord.option(name="exts", type=str, description="extension name to reload", required=False)
    async def reload_ext(ctx: bridge.BridgeContext, *, exts=None):
        await ctx.reply("Reloading extensions")
        if ctx.author.id not in ctx.bot.owner_ids:
            raise commands.NotOwner
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
