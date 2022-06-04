import asyncio
import datetime
import discord
import typing as t

from discord.ext import tasks, commands
from db import (
    fetchguild,
    fetchip,
    fetchuser,
    getnotify,
    gettracking,
    iterdb,
    updateserver,
    updatetracking,
)
from ipaddress import ip_address
from logs import setlog
from discord import MISSING
from enums import *
from source_query import CheckServer
from aiomysql import OperationalError

_logger = setlog(__name__)


class EditMsg(tasks.Loop):
    def __init__(
        self,
        guild: int,
        ip: str,
        message: int,
        channel: discord.TextChannel,
        embed: discord.Embed,
        view: discord.ui.View,
    ) -> None:
        self.guild = guild
        self.ip = ip
        self.message = message
        self.channel = channel
        self.embed = embed
        self.view = view
        super().__init__(
            coro=self.editmsg,
            seconds=1,
            hours=MISSING,
            minutes=MISSING,
            time=MISSING,
            count=None,
            reconnect=True,
            loop=asyncio.get_event_loop(),
        )

    async def editmsg(self):

        _st = datetime.datetime.now()
        msg: discord.PartialMessage = self.channel.get_partial_message(self.message)
        try:
            await msg.edit(embed=self.embed)
        except discord.NotFound:
            try:
                msg = await self.channel.send(embed=self.embed, view=self.view)
            except discord.Forbidden:
                _logger.warning(f"Cannot send tracking message to {self.channel.id}")
                return
            except Exception as e:
                _logger.error(f"Cannot send message on {self.channel.id} with error: {e}")
            await updatetracking(self.guild, self.ip, msg.id)
        except Exception as e:
            _logger.error(f"Cannot edit message on {self.ip} with error: {e}")
        _et = datetime.datetime.now()
        self.stop()
        # _logger.debug(_et-_st)


class ServerTask(tasks.Loop):
    def __init__(
        self,
        bot: commands.Bot,
        name: str,
        ipport: str,
        seconds: float,
        view: discord.ui.View,
        count: t.Optional[int | None] = None,
        reconnect: bool = True,
    ):

        self.bot = bot
        self.mapname = "Unknown!"
        self.msg_id = None
        self.name = name
        self.ipport = ipport

        self.playedtime = 0

        self.isonline = False
        self.svname = None
        self.serverinfo = None

        self._notif = True
        self._retries = 0
        self._view = view
        self._timedout = False
        self._down = False
        self._msgs = {}

        super().__init__(
            coro=self.servercheck,
            seconds=seconds,
            hours=MISSING,
            minutes=MISSING,
            time=MISSING,
            count=count,
            reconnect=reconnect,
            loop=asyncio.get_event_loop(),
        )
        self.add_exception_type(OperationalError)
        bot.loop_maptsk[ipport] = self

    def start(self, *args, **kwargs):
        # self.servercheck.start()
        return super().start(*args, **kwargs)

    def before_loop(self):
        self.bot.wait_until_ready()

    async def getstatus(self):
        ip = ip_address(self.ipport.split(":")[0])
        port = int(self.ipport.split(":")[1])

        _server = await CheckServer.GetServer(ip, port)

        return _server.status

    async def servercheck(self):
        _st = datetime.datetime.now()

        self.get_task().set_name(self.ipport)

        ip = ip_address(self.ipport.split(":")[0])
        port = int(self.ipport.split(":")[1])

        _server = await CheckServer.GetServer(ip, port)

        self.isonline = _server.status

        server_info = discord.Embed()
        server_info.title = _server.name
        self.svname = _server.name

        if self.mapname != _server.maps and _server.status:
            self.mapname = _server.maps
            self.playedtime = round(datetime.datetime.now().timestamp())
            self._notif = False
            if self.serverinfo:
                _history = discord.Embed()
                _history.title = _server.name + " Map history"
                _history.add_field(name=_server.maps, value=f"<t:{self.playedtime}:R>", inline=False)
                _hdict = {self.playedtime: _history.to_dict()}
                # updateserver(self.ipport, _hdict)

        fields = [
            (
                "Status : ",
                Status.ONLINE.value if self.isonline else Status.OFFLINE.value,
                True,
            ),
            # ("Location : ", f"{_server.flag} {_server.location}", True),
            (
                "Quick Connect : ",
                f"steam://connect/{_server.ip_port[0]}:{_server.ip_port[1]}",
                False,
            ),
            ("Map : ", _server.maps, True),
            ("Players : ", f"{_server.players}/{_server.maxplayers}", True),
            ("Map played: ", f"<t:{self.playedtime}:R>", False),
        ]

        for (
            _name,
            _value,
            _inline,
        ) in fields:
            server_info.add_field(name=_name, value=_value, inline=_inline)

        # server_info.set_thumbnail(url="https://media.discordapp.net/attachments/640576623812280321/944140586464710656/unknown.png")
        server_info.timestamp = discord.utils.utcnow()

        self.serverinfo = server_info.to_dict()

        if not _server.status:
            self._retries += 1
        else:
            self._retries = 0

        if self._retries >= 10 and _server.status:
            _logger.info(f"Connection established for {self.ipport}")

        async for _, guild, channel, tracking_ip, message in iterdb(await fetchip(self.ipport)):
            channel: discord.TextChannel = self.bot.get_channel(channel)
            if not channel:
                continue

            guild_message = EditMsg(guild, tracking_ip, message, channel, server_info, self._view)
            # if not guild in self._msgs:
            #     self._msgs[guild] = EditMsg(guild, tracking_ip, message, channel, server_info, self._view)
            #     _logger.debug(f"Added: {tracking_ip} to: {guild} tracking message")
            # guild_message: EditMsg = self._msgs[guild]

            # if channel != guild_message.channel:
            #     guild_message.channel = channel
            #     _logger.debug(f"Updated mesage channel to: {channel} for: {guild}")
            # if message != guild_message.message:
            #     guild_message.message = message
            #     _logger.debug(f"Updated mesage to: {message} for: {guild}")

            if self._retries >= 10:
                if self._retries == 10:
                    _logger.warning(f"Connection Timeout for {self.ipport}")
                    try:
                        guild_message.start()
                    except:
                        pass
                if self._retries == 10080:
                    _logger.critical(f"Shutting down {self.ipport} from map task, failed to respond within a week")
                    try:
                        _msg: discord.Message = self.bot.get_message(message)
                        await _msg.delete()
                    except:
                        _logger.error(f"Cant delete message on {guild}")
                    self.stop()
                continue
            guild_message.start()

        if not self._notif and self.ipport != "103.62.48.10:27058":
            self._notif = True
            async for _, userid, _, _ in iterdb(await fetchuser()):
                _user = self.bot.get_user(userid)
                notif = await getnotify(userid)
                if not _user:
                    continue
                if self.mapname.lower() in notif:
                    try:
                        await _user.send(
                            content="**Your favorite map is being played!**",
                            embed=server_info,
                        )
                    except:
                        _logger.warning(f"Cannot send message to {userid}")
        _et = datetime.datetime.now()
        # _logger.debug(f"Finished looping {self.ipport} in: {_et-_st}")
