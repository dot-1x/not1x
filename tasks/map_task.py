import asyncio
import discord
import typing as t

from discord.ext import tasks, commands
from db import (
    iterdb,
    fetchip,
    fetchuser,
    getnotify,
    updatetracking,
)
from ipaddress import ip_address
from logs import setlog
from discord import MISSING
from enums import *
from source_query import GetServer
from datetime import datetime

_logger = setlog(__name__)


class ServerTask:
    def __init__(
        self,
        bot: commands.Bot,
        name: str,
        ipport: str,
        view: discord.ui.View,
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

        bot.loop_maptsk[ipport] = self

    async def editmsg(
        self,
        guild: int,
        ip: str,
        message: int,
        channel: discord.TextChannel,
        embed: discord.Embed,
        view: discord.ui.View,
    ):
        msg: discord.PartialMessage = channel.get_partial_message(message)
        try:
            await msg.edit(embed=embed)
        except discord.NotFound:
            try:
                msg = await channel.send(embed=embed, view=view)
            except discord.Forbidden:
                _logger.warning(f"Cannot send tracking message to {channel.id}")
                return
            except Exception as e:
                _logger.error(f"Cannot send message on {channel.id} with error: {e}")
            await updatetracking(guild, ip, msg.id)
        except Exception as e:
            pass

    async def servercheck(self):
        _st = datetime.now()

        ip = ip_address(self.ipport.split(":")[0])
        port = int(self.ipport.split(":")[1])

        server_info = await GetServer(ip=str(ip), port=port)

        self.isonline = server_info.status

        if self.mapname != server_info.maps and server_info.status:
            self.mapname = server_info.maps
            self.playedtime = round(datetime.now().timestamp())
            self._notif = False
            if self.serverinfo:
                _history = discord.Embed()
                _history.title = server_info.name + " Map history"
                _history.add_field(name=server_info.maps, value=f"<t:{self.playedtime}:R>", inline=False)
                _hdict = {self.playedtime: _history.to_dict()}

        server_info.add_field(name="Map played: ", value=f"<t:{self.playedtime}:R>", inline=False)

        if not server_info.status:
            self._retries += 1
        else:
            self._retries = 0

        if self._retries >= 10 and server_info.status:
            _logger.info(f"Connection established for {self.ipport}")

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

        async for _, guild, channel, tracking_ip, message in iterdb(await fetchip(self.ipport)):
            channel: discord.TextChannel = self.bot.get_channel(channel)
            if not channel:
                continue

            if self._retries >= 10:
                if self._retries == 10:
                    _logger.warning(f"Connection Timeout for {self.ipport}")
                    try:
                        await asyncio.wait_for(
                            self.editmsg(guild, tracking_ip, message, channel, server_info, self._view), 30
                        )
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
            await asyncio.wait_for(self.editmsg(guild, tracking_ip, message, channel, server_info, self._view), 30)

        _et = datetime.now()
        # _logger.debug(_et - _st)
