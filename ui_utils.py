from __future__ import annotations

import asyncio
import io
import typing as t
from datetime import datetime
from ipaddress import ip_address
from itertools import chain

import discord
import pandas as pd
from discord.ext import commands, pages
from numpy import place

from db import iterdb
from enums import *
from logs import setlog
from source_query import GetServer
from utils import most_color

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
        _sv = await GetServer(self.ip, self.port)
        _pl = await _sv.players()
        if not len(_pl):
            await _interaction.response.send_message("Server doesn't respond or no players online", ephemeral=True)
            return

        _logger.info(f"Sending player list {_sv.ip_port} to {_interaction.user}")

        _players = "\n".join(sorted([p.name.lower() for p in _pl]))

        try:
            await _interaction.user.send(content=f"**{_sv.name}** ({len(_pl)}/{_sv.maxplayers})\n```{_players}```")
        except discord.Forbidden:
            await _interaction.response.send_message("i cant send the players on private message", ephemeral=True)
        except Exception as e:
            _logger.warning(e)
        else:
            await _interaction.response.send_message("Player list send to private message", ephemeral=True)

    async def sendstats(self, _interaction: discord.Interaction):
        await _interaction.response.defer(ephemeral=True)
        _sv = await GetServer(self.ip, self.port)
        if not _sv.status:
            await _interaction.followup.send("Server is offline!", ephemeral=True)
            return
        em = discord.Embed()
        em.title = _sv.name
        em.color = discord.Color.blurple()
        lim = 0
        total_average = []
        async for _, ip, map, date, lastplayed, playtime, played, avg_player in iterdb(
            sorted(await self.bot.db.fetchserverdata(self.ipport), key=lambda x: x[4], reverse=True)
        ):
            if lim > 24:
                break
            em.add_field(
                name=map,
                value=f"Last Played: <t:{round(lastplayed.timestamp())}>\nAverage Players: {avg_player}\nPlayed: {played if played else 1} time(s)\nPlaytime: {playtime} minute(s)",
                inline=True,
            )
            total_average.append(avg_player)
            lim += 1
        em.description = "Total average player(s): " + str(sum(total_average) / len(total_average))
        em.set_footer(text="Note: map playtime stats is generated after map finished playing!")
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
        x = await self.bot.db.fetchserverdata(self.ipport)
        x = [a for a in x if (datetime.now() - a[4]).days < 7]
        data = {}
        for _, ip, Maps, TimePlayed, LastPlayed, PlayTime, Played, AveragePlayers in x:
            if ip not in data:
                data[ip] = {}
            if Maps not in data[ip]:
                data[ip][Maps] = {
                    "Ip": ip,
                    "Map": Maps,
                    "Play_Time": PlayTime,
                    "Played": Played,
                    "Average_Player": [AveragePlayers],
                    "Last_Played": LastPlayed,
                }
            else:
                if data[ip][Maps]["Last_Played"] < LastPlayed:
                    data[ip][Maps]["Last_Played"] = LastPlayed
                data[ip][Maps]["Play_Time"] += PlayTime
                data[ip][Maps]["Played"] += Played
                data[ip][Maps]["Average_Player"].append(AveragePlayers)
        listed = []
        for k in data:
            for m in data[k]:
                listed.append(tuple(data[k][m].values()))
        d = pd.DataFrame(
            listed,
            columns=("Ip", "Maps", "Time Played (minutes)", "Played time", "Average Players", "Last Played (UTC+0)"),
        )
        d = d.sort_values("Time Played (minutes)", ascending=False)
        b = io.BytesIO(bytes(d.to_string(), "utf-8"))
        file = discord.File(b, ip + ".txt")
        try:
            await _interaction.user.send(content="**Note: Data is not 100% accurate**", file=file)
        except discord.Forbidden:
            await _interaction.followup.send("i cant send the week stats on private message", ephemeral=True)
        except Exception as e:
            _logger.warning(e)
        else:
            _logger.info(f"server week stats {self.ipport} send to {_interaction.user}")
            await _interaction.followup.send(content="Server week stats send to private message", ephemeral=True)


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

    page.disable_all_items()
    _c.disable_all_items()
    
    selected = list(chain.from_iterable([v for v in page.selected.values()]))
    embed.title = "Selected Map" if len(selected) > 1 else "No map were selected!"

    embed.description = "\n".join([a for a in selected])
    if not _c.cancel and len(selected) > 0:
        await bot.db.insertnotify(ctx.author.id, ctx.author, selected, delete=edit)
    if _c.cancel:
        embed.title = "Option Canceled!"
        embed.description = embed.Empty

    await ctx.edit(view=page, embed=embed)
    await _confirm.edit(view=_c)

    page.stop()


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

    page.disable_all_items()
    _c.disable_all_items()

    selected = list(chain.from_iterable([v for v in page.selected.values()]))
    embed.title = "Selected IP" if len(selected) > 1 else "No IP were selected!"

    embed.description = "\n".join([a for a in selected])
    if not _c.cancel and len(selected) > 0:
        for ip in selected:
            await bot.db.deletetracking(ctx.guild.id, ip)
    if _c.cancel:
        embed.title = "Option Canceled!"
        embed.description = embed.Empty

    await ctx.edit(view=page, embed=embed)
    await _confirm.edit(view=_c)

    page.stop()
