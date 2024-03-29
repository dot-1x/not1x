from __future__ import annotations

import asyncio
import re
import typing as t
from datetime import datetime
from ipaddress import ip_address

import discord
import numpy as np

from enums import *
from logs import setlog
from source_query import GetServer
from utils import log_exception

if t.TYPE_CHECKING:
    import not1x

_logger = setlog(__name__)


class ServerTask:
    def __init__(
        self,
        bot: not1x.Bot,
        name: str,
        ipport: str,
        view: discord.ui.View,
    ):

        self.bot = bot
        self.mapname = MapEnum.UNKOWN
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

        self._players = [0]

        self._maptime = datetime.now()

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
            await msg.edit(embed=embed, view=view)
        except discord.NotFound:
            try:
                msg = await channel.send(embed=embed, view=view)
                await self.bot.db.updatetracking(guild, ip, msg.id)
            except discord.Forbidden:
                _logger.warning(f"Cannot send tracking message to {channel.id}")
            except TimeoutError:
                _logger.critical(f"Failed to update to database")
            except Exception as e:
                _logger.error(f"Cannot update message on {channel.id} with error: {e}")
        except discord.Forbidden:
            pass
        except Exception as e:
            log_exception(e, base_err)

    async def servercheck(self) -> None:
        _st = datetime.now()
        self.mapname = await self.bot.db.getlastmap(self.ipport)
        ip = ip_address(self.ipport.split(":")[0])
        port = int(self.ipport.split(":")[1])

        server_info = await GetServer(ip=str(ip), port=port)

        self.isonline = server_info.status

        date_now = _st.strftime("%Y-%m-%d")
        if self.mapname != server_info.maps and server_info.status:

            await self.bot.db.updateserver(self.ipport, server_info.maps, date_now)
            await self.bot.db.updatelastmap(self.ipport, server_info.maps, round(_st.timestamp()))

            self._notif = False
            self.mapname = server_info.maps
            self._players.clear()

        self.playedtime = round(await self.bot.db.getlastmaptime(self.ipport))
        self._maptime = datetime.fromtimestamp(self.playedtime)
        self._players.append(server_info.player)
        await self.bot.db.updateplayers(self.ipport, self.mapname, date_now, round(np.average(self._players)))
        await self.bot.db.updatemaptime(self.ipport, self.mapname, date_now, (_st - self._maptime).seconds / 60)

        server_info.add_field(name="Map played: ", value=f"<t:{self.playedtime}:R>", inline=False)

        if self._retries >= 10 and server_info.status:
            _logger.info(f"Connection established for {self.ipport}")

        if not server_info.status:
            self._retries += 1
        else:
            self._retries = 0

        if not self._notif and self.ipport != "103.62.48.10:27058" and self.isonline:
            self._notif = True
            async for userid in self.bot.db.fetchuserid():
                _user = self.bot.get_user(userid)
                if not _user:
                    continue
                async for map in self.bot.db.getnotify(userid):
                    if not re.search(map.lower(), self.mapname.lower()):
                        continue
                    await asyncio.wait_for(_user.send(embed=server_info), timeout=30)

        async for _, guild, channel, tracking_ip, message in self.bot.db.fetchip(self.ipport):
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
                    self.bot.server_task[self.ipport].stop()
                continue
            await asyncio.wait_for(self.editmsg(guild, tracking_ip, message, channel, server_info, self._view), 30)

        _et = datetime.now()
        # _logger.debug(_et - _st)
