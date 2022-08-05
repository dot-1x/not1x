from __future__ import annotations

import asyncio
import io
import traceback
import typing as t
from datetime import datetime
from ipaddress import ip_address

import discord

from enums import *
from logs import setlog
from source_query import GetServer

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

        self._players = []

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
            with open("logs/traceback.log", "a") as f:
                traceback.print_exc(file=f)
            _logger.error(e)

    async def notifyuser(self, user: discord.User, userid: int, embed: discord.Embed, maps: list):
        if self.mapname.lower() in maps:
            try:
                await user.send(
                    embed=embed,
                )
            except:
                _logger.warning(f"Cannot send message to {userid}")

    async def servercheck(self) -> None:
        """
        TO DO:
        Fix Playtime
        """
        _st = datetime.now()

        self.mapname = await self.bot.db.getlastmap(self.ipport)
        _logger.debug(self.mapname)
        ip = ip_address(self.ipport.split(":")[0])
        port = int(self.ipport.split(":")[1])

        server_info = await GetServer(ip=str(ip), port=port)

        self.isonline = server_info.status

        date_now = _st.strftime("%Y-%m-%d")
        if self.mapname != server_info.maps and server_info.status:
            if self.mapname != MapEnum.UNKOWN:
                self._maptime = _st - self._maptime
                _sumplayers = sum(self._players)
                await self.bot.db.updateserver(  # update old map to db
                    self.ipport,
                    self.mapname,
                    date_now,
                    round(self._maptime.seconds / 60),
                    round(_sumplayers / len(self._players) if _sumplayers else 0),
                )
                await self.bot.db.updateserver(self.ipport, server_info.maps, date_now)  # update new maps to db
            else:
                await self.bot.db.updateserver(self.ipport, server_info.maps, date_now)

            self._maptime = _st
            self.playedtime = round(datetime.now().timestamp())
            self._notif = False
            self.mapname = server_info.maps
            self._players.clear()

        self._players.append(server_info.player)
        _sumplayers = sum(self._players)
        await self.bot.db.updateplayers(
            self.ipport, self.mapname, date_now, round(_sumplayers / len(self._players) if _sumplayers else 0)
        )

        server_info.add_field(name="Map played: ", value=f"<t:{self.playedtime}:R>", inline=False)

        if self._retries >= 10 and server_info.status:
            _logger.info(f"Connection established for {self.ipport}")

        if not server_info.status:
            self._retries += 1
        else:
            self._retries = 0

        if not self._notif and self.ipport != "103.62.48.10:27058" and self.isonline:
            self._notif = True
            async for _, userid, _, _ in await self.bot.db.fetchuser():
                _user = self.bot.get_user(userid)
                notif = await self.bot.db.getnotify(userid)
                if not _user:
                    continue

                self.bot.loop.run_in_executor(None, self.notifyuser, (_user, userid, server_info, notif))

        async for _, guild, channel, tracking_ip, message in await self.bot.db.fetchip(self.ipport):
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
