import asyncio
import json
import pathlib
import traceback
import typing as t
import os
import discord
import ui_utils


from tasks.map_task import ServerTask
from datetime import datetime
from db import getserverdata, loadguild, connection
from enums import *
from logs import setlog
from discord.ext import bridge, commands, tasks
from discord.ext.commands.errors import *
from command_error import CheckError, StdErrChannel
from ipaddress import ip_address

__version__ = "0.4"
__all__ = ["Bot"]

_logger = setlog(__name__)


class CustomHelp(commands.HelpCommand):
    def __init__(self, **options):
        super().__init__(**options)

    async def send_bot_help(self, mapping: t.Mapping[t.Optional[commands.Cog], t.List[commands.Command]]):
        _logger.debug(mapping)
        await self.context.send(content="A help command passed!")


class Bot(bridge.Bot):
    def __init__(self, config: dict, *, token: str):
        self.prefix = "]"
        self.ready = False
        self.help = CustomHelp()
        self.config = config
        self.__token = token
        self._fail_connect = False
        super().__init__(
            command_prefix=self.prefix,
            owner_ids=Data.OWNER.value,
            case_insensitive=True,
            intents=discord.Intents.all(),
            help_command=self.help,
        )
        _logger.info("++++++ Loading not1x ++++++")
        _logger.info(f"Version: {__version__}")
        try:
            loop = asyncio.get_event_loop()
            loop.run_until_complete(connection.conn())
        except:
            _logger.critical("Failed to connect to database")
            self._fail_connect = True

        self._pl_list_button = False
        self._persiew = {}
        self.loop_maptsk = {}

        self.load_extension_from("cogs")
        # self.load_extension("utils")
        self.add_bridge_command(self.reload_ext)

    def run(self):
        if self._fail_connect:
            _logger.error("Connection is failed!")
            self.loop.stop()
            return
        super().run(self.__token)

    def map_tasks(self):
        _sv_list = self.config["serverquery"]
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

            ServerTask(self, _sv, _sv, self.persview[_sv])

        @tasks.loop(seconds=60)
        async def globalqueryloop():
            _s = datetime.now()
            # _logger.debug(f"Started loop at: {_s.__str__()}")
            for l in self.loop_maptsk.values():
                l: ServerTask
                await asyncio.wait_for(l.servercheck(), 60)
            _e = datetime.now()
            # _logger.debug(f"Loop ended at: {_e.__str__()}")
            # _logger.debug(f"Loop done in: {_e - _s}")

        @globalqueryloop.error
        async def on_loop_err(error: discord.DiscordException):
            _logger.error(f"global loop encountered an error: {error}")
            with open("logs/traceback.log", "a") as f:
                f.write(str(datetime.utcnow()) + "\n" + str(error.with_traceback(error.__traceback__)) + "\n")
                traceback.print_tb(error.__traceback__, file=f)

        globalqueryloop.start()
        globalqueryloop.get_task().set_name("globalqueryloop")

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
                await loadguild(guild.id)
            except:
                _logger.critical("Failed to load guild from database")
                self.loop.stop()

        self.map_tasks()

        for c in self.cogs:
            _logger.info(f"Loaded cog: {c}")

        _logger.info(f"++++++ Successfully Logged in as: {self.user} ++++++")

    async def on_disconnect():
        _logger.info("Bot has been disconnected from discord")

        return super().on_disconnect()

    async def on_guild_join(self, guild: discord.Guild):
        await loadguild(guild.id)
        return super().on_guild_join(guild)

    async def on_message(self, message: discord.Message = None):
        try:
            if message.channel.id == Data.STD_ERR_CHANNEL.value and not message.author.bot:
                await message.delete()
                raise StdErrChannel
        except StdErrChannel:
            _logger.warning(StdErrChannel)
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
    @commands.cooldown(1, 15, commands.BucketType.user)
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
