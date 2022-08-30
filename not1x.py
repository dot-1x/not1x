from itertools import chain
import typing as t
from ipaddress import ip_address

import discord
from discord.ext import bridge, commands, tasks
from discord.ext.commands.errors import *

import ui_utils
from command_error import CheckError
from db import connection
from enums import *
from logs import setlog
from tasks.map_task import ServerTask
from utils import log_exception

__version__ = "0.6.8"

_logger = setlog(__name__)


class Bot(bridge.Bot):
    def __init__(self, config: dict, *, token: str, db: connection, debug: bool = False):
        self.prefix = "."
        self.ready = False
        self.config = config
        self.debug = debug
        self.__token = token
        intent = discord.Intents(guilds=True, members=True, messages=True, presences=True)

        super().__init__(
            command_prefix=self.prefix,
            owner_ids=Data.OWNER.value,
            case_insensitive=True,
            intents=intent,
            help_command=None,
        )
        _logger.info("++++++ Loading not1x ++++++")
        _logger.info(f"Version: {__version__}")

        self._pl_list_button = False
        self._persiew: t.Dict[str, ui_utils.PlayerListV] = {}
        self.server_task: t.Dict[str, tasks.Loop] = {}

        self.exts = self.load_extension("cogs", recursive=True, store=True)
        self._failed_exts = [k for k, v in self.exts.items() if isinstance(v, Exception)]
        self._loaded_exts = [k for k, v in self.exts.items() if v is True]
        self.db = db

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

        for c in self.cogs:
            _logger.info(f"Loaded cog: {c}")
        _logger.info(f"Failed cogs: {self._failed_exts}")

        loaded_guilds =  await self.db.execute("SELECT `guild_id` FROM `guild_tracking`", fetch=True, fetchall=True, res=True)
        loaded_guilds: t.List[int] = list(dict.fromkeys(chain.from_iterable(loaded_guilds)))
        guilds = await self.fetch_guilds().flatten()
        for guild in guilds:
            if not guild.id in loaded_guilds:
                try:
                    await self.db.loadguild(guild.id)
                except Exception as e:
                    _logger.critical("Failed to load guild from database")
                    log_exception(e, base_err)
                    self.loop.stop()
                else:
                    loaded_guilds.append(guild.id)
        g_ids = [i.id for i in guilds]
        for g_id in loaded_guilds:
            if g_id in g_ids:
                continue
            else:
                await self.db.deleteguild(g_id)

        if self.debug:
            _logger.warning("++++++ DEBUG MODE ENABLED +++++")
        else:
            await self.map_tasks()

        _logger.info(f"++++++ Successfully Logged in as: {self.user} ++++++")

    async def on_guild_join(self, guild: discord.Guild):
        _logger.info(f"Bot has joined guild: {guild.name}({guild.id})")
        try:
            await self.db.loadguild(guild.id)
        except:
            _logger.error("Failed to insert guild to database")

    async def on_guild_remove(self, guild: discord.Guild):
        _logger.info(f"Bot has leaving guild {guild.name}({guild.id})")
        await self.db.deleteguild(guild.id)

    async def on_application_command_error(self, ctx: discord.ApplicationContext, err: discord.DiscordException):
        await CheckError(ctx, err)

    async def on_command_error(self, ctx: commands.Context, err: commands.CommandError):
        await CheckError(ctx, err)

    ####################### End of bot event handler #######################
    def reload_extension(self, name: t.Optional[str] = None, *, package: t.Optional[str] = None) -> None:
        if name is None:
            self._failed_exts.clear()
            for k, v in self.exts.items():
                if isinstance(v, Exception):
                    try:
                        self.load_extension(k, store=False)
                    except Exception as e:
                        _logger.error(f"'{k}' Throwing an error while loading")
                        self.exts[k] = v
                        self._failed_exts.append(k)
                        log_exception(e, base_err)
                    else:
                        _logger.info(f"Loaded Extension: {k}")
                        self.exts[k] = True
                else:
                    try:
                        super().reload_extension(k)
                    except Exception as e:
                        _logger.error(f"'{k}' Throwing an error while reloading")
                        log_exception(e, base_err)
                        self._failed_exts.append(k)
                    else:
                        _logger.info(f"Reloaded Extension: {k}")
            return
        return super().reload_extension(name, package=package)
