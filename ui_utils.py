from __future__ import annotations

import asyncio
import io
import typing as t
from datetime import datetime
from ipaddress import ip_address
from itertools import chain

import discord
import numpy as np
import pandas as pd

from db import iterdb
from enums import *
from logs import setlog
from source_query import GetServer
from utils import most_color, parse_history

if t.TYPE_CHECKING:
    import not1x

_logger = setlog(__name__)


class PlayerListV(discord.ui.View):
    def __init__(self, bot: not1x.Bot, ip: str, port: int):

        self.ip = ip_address(ip)
        self.port = port
        self.ipport = f"{ip}:{port}"
        self.bot = bot

        super().__init__(timeout=None)
        self.buttons = {
            "Players": {"callback": self.sendplayer, "label": "Player List", "style": discord.ButtonStyle.secondary},
            "Stats": {"callback": self.sendstats, "label": "Server History", "style": discord.ButtonStyle.green},
            "WeekStats": {"callback": self.weekstats, "label": "Server Stats", "style": discord.ButtonStyle.primary},
        }
        for btn in self.buttons:
            _btn = discord.ui.Button(
                label=self.buttons[btn]["label"], style=self.buttons[btn]["style"], custom_id=f"{ip}:{port}:{btn}"
            )
            _btn.callback = self.buttons[btn]["callback"]
            self.add_item(_btn)

    async def sendplayer(self, _interaction: discord.Interaction):
        await _interaction.response.defer(ephemeral=True)
        _sv = await GetServer(self.ip, self.port)
        _pl = await _sv.players()
        if not len(_pl):
            await _interaction.followup.send(content="Server doesn't respond or no players online", ephemeral=True)
            return

        _logger.info(f"Sending player list {_sv.ip_port} to {_interaction.user}")

        _players = "\n".join(sorted([p.name.lower() for p in _pl]))

        try:
            await _interaction.user.send(content=f"**{_sv.name}** ({len(_pl)}/{_sv.maxplayers})\n```{_players}```")
        except discord.Forbidden:
            await _interaction.followup.send(content="i cant send the players on private message", ephemeral=True)
        except Exception as e:
            _logger.warning(e)
        else:
            await _interaction.followup.send(content="Player list send to private message", ephemeral=True)

    async def sendstats(self, _interaction: discord.Interaction):
        await _interaction.response.defer(ephemeral=True)
        _sv = await GetServer(self.ip, self.port)
        if not _sv.status:
            await _interaction.followup.send("Server is offline!", ephemeral=True)
            return
        em = discord.Embed()
        em.title = _sv.name
        em.color = discord.Color.blurple()

        data = await self.bot.db.fetchserverdata(self.ipport)

        data = data[:24]

        listed = list(parse_history(data))
        for l in listed:
            em.add_field(
                name=l["Map"],
                value=f"Last Played: <t:{round(l['Last_Played'].timestamp())}>\nAverage Players: {l['Average_Player']}\nPlayed: {l['Played']} time(s)\nPlaytime: {l['Play_Time']} minute(s)",
                inline=True,
            )
        total_average = [a["Average_Player"] for a in listed]
        em.description = f"Total average player(s): {np.average(total_average)}"
        try:
            await _interaction.user.send(embed=em)
        except discord.Forbidden:
            await _interaction.followup.send("i cant send the stats on private message", ephemeral=True)
        except Exception as e:
            _logger.warning(e)
        else:
            _logger.info(f"server stats {self.ipport} send to {_interaction.user}")
            await _interaction.followup.send(content="Server stats send to private message", ephemeral=True)

    async def weekstats(self, _interaction: discord.Interaction):
        await _interaction.response.defer(ephemeral=True)
        data = await self.bot.db.fetchserverdata(self.ipport)

        def sortday():
            return [a for a in data if (datetime.now() - a.lastplayed).days < 7]

        data = await self.bot.loop.run_in_executor(None, sortday)

        listed = list(parse_history(data))
        total_average = [a["Average_Player"] for a in listed]

        df = pd.DataFrame(
            listed,
            index=None,
        )
        df = df.sort_values("Play_Time", ascending=False, ignore_index=True)
        stringdata = (
            f"Playtime is in minutes, Date are UTC+0\n\nServer IP: {self.ipport}\nTotal Average Players: {np.average(total_average):.2f}\nSorted By Most PlayTime\n"
            + df.to_string()
        )
        b = io.BytesIO(bytes(stringdata, "utf-8"))
        file = discord.File(b, self.ipport + ".txt")
        try:
            await _interaction.user.send(content="**Note: Data is not 100% accurate**", file=file)
        except discord.Forbidden:
            await _interaction.followup.send("i cant send the week stats on private message", ephemeral=True)
        except Exception as e:
            _logger.warning(e)
        else:
            _logger.info(f"server week stats {self.ipport} send to {_interaction.user}")
            await _interaction.followup.send(content="Server week stats send to private message", ephemeral=True)
        finally:
            b.close()
            file.close()
            del b
            del file


class Confirm(discord.ui.View):
    def __init__(self, author: discord.Member = None, timeout: float = 180):
        self.author = author
        self.cancel = True
        super().__init__(timeout=timeout)

    @discord.ui.button(label="CONFIRM", style=discord.ButtonStyle.green)
    async def _confirm(self, _select, _interact: discord.Interaction):
        if self.author != _interact.user:
            await _interact.response.send_message(content="This confirmation is not for you!", ephemeral=True)
            return
        await _interact.response.edit_message(content="Option CONFIRMED!")
        self.cancel = False
        self.stop()

    @discord.ui.button(label="CANCEL", style=discord.ButtonStyle.red)
    async def _cancel(self, _select, _interact: discord.Interaction):
        if self.author != _interact.user:
            await _interact.response.send_message(content="This confirmation is not for you!", ephemeral=True)
            return
        await _interact.response.edit_message(content="Option CANCELED!")
        self.cancel = True
        self.stop()


class ChooseView(discord.ui.Select["PageUi"]):
    def __init__(
        self,
        author: discord.Member,
        options: t.List[discord.SelectOption],
        title: str,
        val: int,
    ):
        self.author = author
        self.opt_ = options
        self.title = title
        self.value = val
        super().__init__(placeholder=title, min_values=0, max_values=len(self.opt_), options=self.opt_)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user != self.author:
            interaction.response.send_message("This is not for you!")
            return
        await interaction.response.send_message(content=f"Selected items: {sorted(self.values)}", ephemeral=True)
        self.view.selected[f"Select{self.value}"] = self.values


class PageUi(discord.ui.View):
    def __init__(self, author: discord.Member, title: str, options: t.List[ChooseView], timeout: float = 180) -> None:
        super().__init__(timeout=timeout)
        self.author = author
        self.options = options
        self.selected = {}

        self.opt = [discord.SelectOption(label=a.title, value=str(a.value)) for a in options]
        self.select = discord.ui.Select(placeholder=title, min_values=1, max_values=1, options=self.opt)
        self.select.callback = self.select_callback

        self.add_item(self.select)

    async def select_callback(self, interact: discord.Interaction):
        if interact.user != self.author:
            interact.response.send_message("This is not for you!")
            return
        _selected: ChooseView = self.options[int(self.select.values[0])]
        self.clear_items()
        self.add_item(self.select)

        if f"Select{_selected.value}" in self.selected:
            _opt = _selected.options
            _selected = ChooseView(
                self.author,
                [
                    discord.SelectOption(
                        label=a.label,
                        value=a.value,
                        default=True if a.value in self.selected[f"Select{_selected.value}"] else False,
                    )
                    for a in _opt
                ],
                _selected.title,
                _selected.value,
            )

        self.add_item(_selected)
        await interact.response.edit_message(view=self)


async def select_map(ctx: discord.ApplicationContext, opt: t.List[discord.SelectOption], edit: bool = False):
    views = []
    bot: not1x.Bot = ctx.bot
    for num, x in enumerate(range(0, len(opt), 25)):
        _opt = opt[x : x + 25]
        views.append(ChooseView(ctx.author, _opt, title=f"Select Map {num+1}", val=num))
    page = PageUi(ctx.author, title="Select Page", options=views)
    embed = discord.Embed(
        title="Please Choose a map to update",
        color=await most_color(ctx.author.avatar),
        timestamp=discord.utils.utcnow(),
    )
    embed.set_author(name=ctx.author.name, icon_url=ctx.author.avatar.url if ctx.author.avatar.url else embed.Empty)
    await ctx.respond(view=page, embed=embed)

    _c = Confirm(ctx.author, 60)

    _confirm = await ctx.respond(content="Press Confirm to update current notification list", view=_c, ephemeral=True)
    await _c.wait()

    selected = list(chain.from_iterable([v for v in page.selected.values()]))
    embed.title = "Selected Map" if len(selected) > 0 else "No map were selected!"

    embed.description = "\n".join([a for a in selected])
    if not _c.cancel and len(selected) > 0:
        await bot.db.insertnotify(ctx.author.id, ctx.author, selected, delete=edit)
    if _c.cancel:
        embed.title = "Option Canceled!"
        embed.description = embed.Empty

    page.stop()
    page.disable_all_items()
    await ctx.edit(view=page, embed=embed)


async def select_ip(ctx: discord.ApplicationContext, opt: t.List[discord.SelectOption], edit: bool = False):
    views = []
    bot: not1x.Bot = ctx.bot
    for num, x in enumerate(range(0, len(opt), 25)):
        _opt = opt[x : x + 25]
        views.append(ChooseView(ctx.author, _opt, title=f"Select IP {num+1}", val=num))
    page = PageUi(ctx.author, title="Select IP", options=views)
    embed = discord.Embed(
        title="Please Choose an IP to update",
        color=await most_color(ctx.author.avatar),
        timestamp=discord.utils.utcnow(),
    )
    embed.set_author(name=ctx.author.name, icon_url=ctx.author.avatar.url if ctx.author.avatar.url else embed.Empty)
    await ctx.respond(view=page, embed=embed)

    _c = Confirm(ctx.author, 60)

    _confirm = await ctx.respond(content="Press Confirm to update selected IP from guild", view=_c, ephemeral=True)
    await _c.wait()

    selected = list(chain.from_iterable([v for v in page.selected.values()]))
    embed.title = "Selected IP" if len(selected) > 0 else "No IP were selected!"

    embed.description = "\n".join([a for a in selected])
    if not _c.cancel and len(selected) > 0:
        for ip in selected:
            await bot.db.deletetracking(ctx.guild.id, ip)
    if _c.cancel:
        embed.title = "Option Canceled!"
        embed.description = embed.Empty

    page.disable_all_items()
    page.stop()
    await ctx.edit(view=page, embed=embed)
