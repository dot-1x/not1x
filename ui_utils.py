from __future__ import annotations

import typing as t
from datetime import datetime
from ipaddress import ip_address
from itertools import chain

import discord
from discord.ext import commands, pages

from db import *
from enums import *
from logs import setlog
from source_query import GetServer

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
        btn = discord.ui.Button(
            custom_id=f"{ip}:{port}:Players",
            style=discord.ButtonStyle.secondary,
            label="Player List",
        )
        btn.callback = self.sendplayer
        btn2 = discord.ui.Button(
            custom_id=f"{ip}:{port}:Stats",
            style=discord.ButtonStyle.primary,
            label="Server Stats",
        )
        btn.callback = self.sendplayer
        btn2.callback = self.sendstats
        self.add_item(btn)
        self.add_item(btn2)

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
        await _interaction.response.send_message("Sending stats...", ephemeral=True)
        _sv = await GetServer(self.ip, self.port)
        em = discord.Embed()
        em.title = _sv.name
        em.color = discord.Color.blurple()
        lim = 0
        async for _, ip, map, date, lastplayed, playtime, played, avg_player in iterdb(sorted(await fetchserverdata(self.ipport), key=lambda x: x[4], reverse=True)):
            if lim > 24: break
            em.add_field(name=map, value=f"Last Played: <t:{round(lastplayed.timestamp())}>\nAverage Players: {avg_player}\nPlayed: {played}", inline=False)
            lim += 1
        try:
            await _interaction.user.send(embed=em)
        except discord.Forbidden:
            await _interaction.response.send_message("i cant send the stats on private message", ephemeral=True)
        except Exception as e:
            _logger.warning(e)
        else:
            _logger.info(f"server stats {self.ipport} send to {_interaction.user}")
            await _interaction.response.send_message(content="Server stats send to private message", ephemeral=True)


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
        self.cancel = False
        self.stop()

    @discord.ui.button(label="CANCEL", style=discord.ButtonStyle.red)
    async def _cancel(self, _select, _interact: discord.Interaction):
        if self.author != _interact.user:
            await _interact.response.send_message(content="This confirmation is not for you!", ephemeral=True)
            return
        self.cancel = True
        self.stop()


class ChooseView(discord.ui.View):
    def __init__(
        self,
        author: discord.Member,
        options: t.List[discord.SelectOption],
        ui_placeholder: str,
        max_val: int = 25,
        min_val: int = 1,
        msg: discord.Message = None,
        embed: discord.Embed = None,
    ):
        self.author = author
        self.selectedval = []
        self.msg = msg
        self.embed = embed
        super().__init__(timeout=180)
        select_opt = discord.ui.Select(
            placeholder=ui_placeholder, max_values=max_val, min_values=min_val, options=options
        )
        select_opt.callback = self.interact
        self.add_item(select_opt)

    async def interact(self, _select: discord.ui.Select, _interact: discord.Interaction):
        if _interact.user != self.author:
            return
        self.selectedval = _select.values
        em: discord.Embed = self.msg.embeds[0]
        desc = em.description
        print(desc)


class GeneratePage(pages.Paginator):
    def __init__(
        self,
        options: t.List[discord.SelectOption],
        pages: t.List[str] | t.List[pages.Page] | t.List[t.List[discord.Embed] | discord.Embed],
    ) -> None:
        super().__init__()
        pages.PageGroup(
            pages=pages,
        )


async def view_select_map(
    ctx: discord.ApplicationContext,
    _options: t.List[discord.SelectOption],
    notify: bool,
):
    _pages = []
    _selected_val = {}
    _uis = []
    embeds = discord.Embed()
    embeds.title = "SELECTED MAPS:"
    _pnum = 0

    if len(_options) < 1:
        await ctx.respond("None map found!")
        return

    for x in range(0, len(_options), 25):
        _opt = _options[x : x + 25]
        _pnum += 1

        class ChooseView(discord.ui.View):
            def __init__(self, _author: discord.Member):
                self.author = _author
                self.selectedval = []
                self.msg = None
                super().__init__(timeout=180)

            def set_msg(self, msg: discord.Message):
                self.msg = msg

            @discord.ui.select(
                placeholder="select map",
                min_values=0,
                max_values=len(_opt),
                options=_opt,
            )
            async def interact(self, _select: discord.ui.Select, _interact: discord.Interaction):
                if _interact.user != self.author:
                    return
                self.selectedval = _select.values
                _selected_val[self] = _select.values
                embeds.description = f"```{list(chain.from_iterable([v for v in _selected_val.values()]))}```"
                await self.msg.edit(embed=embeds)

        ui_view = ChooseView(ctx.author)
        _pgroup = pages.PageGroup(
            pages=[
                f"Map Page {_pnum}\n**NOTE: If you switch to another page, you will have to set up again on current page!**"
            ],
            label=f"Select map page {_pnum}",
            description=f"Data will be saved after you select map",
            custom_view=ui_view,
            author_check=True,
        )
        _pages.append(_pgroup)
        _uis.append(ui_view)
    _confirm = Confirm(ctx.author, 180)
    _paginator = pages.Paginator(pages=_pages, show_menu=True, author_check=True)
    await _paginator.respond(ctx.interaction, ephemeral=False)
    msg = await ctx.respond(
        "Press Confirm to {} selected maps {} notification list".format(
            "add" if notify else "delete", "to" if notify else "from"
        ),
        view=_confirm,
        ephemeral=True,
    )
    for _ui_select in _uis:
        _ui_select.set_msg(msg)
    await _confirm.wait()
    _selected_map = list(chain.from_iterable([v for v in _selected_val.values()]))
    if _confirm.cancel or len(_selected_val) <= 0:
        await ctx.respond("Option canceled", ephemeral=True)
        embeds.title = "No map were {}".format("notified" if notify else "deleted")
        embeds.description = None
    else:
        await insertnotify(ctx.author.id, ctx.author, _selected_map, delete=not notify)
        await ctx.respond(
            content="Succesfully {} map notification:\n```{}```".format(
                "added to" if notify else "deleted from", _selected_map
            ),
            ephemeral=True,
        )
        embeds.title = "Notified Maps:" if notify else "Deleted maps: "

    embeds.color = ctx.author.color
    embeds.set_author(name=ctx.author)
    await _paginator.disable(include_custom=True, page=embeds)
    _confirm.stop()
    _paginator.stop()


async def view_select_server_query(ctx: discord.ApplicationContext, _options: t.List[discord.SelectOption]):

    _pages = []
    _selected_val = {}
    _uis = []
    embeds = discord.Embed()
    embeds.title = "SELECTED IP:"
    _pnum = 0

    if len(_options) < 1:
        await ctx.respond("None query found!")
        return

    for x in range(0, len(_options), 25):
        _opt = _options[x : x + 25]
        _pnum += 1

        class ChooseView(discord.ui.View):
            def __init__(self, _author: discord.Member):
                self.author = _author
                self.selectedval = []
                self.msg = None
                super().__init__(timeout=180)

            def set_msg(self, msg: discord.Message):
                self.msg = msg

            @discord.ui.select(
                placeholder="select IP",
                min_values=0,
                max_values=len(_opt),
                options=_opt,
            )
            async def interact(self, _select: discord.ui.Select, _interact: discord.Interaction):
                if _interact.user != self.author:
                    return
                self.selectedval = _select.values
                _selected_val[self] = _select.values
                embeds.description = f"```{list(chain.from_iterable([v for v in _selected_val.values()]))}```"
                await self.msg.edit(embed=embeds)
                return _interact.response.is_done()

        ui_view = ChooseView(ctx.author)
        _pgroup = pages.PageGroup(
            pages=[
                f"Page {_pnum}\n**NOTE: If you switch to another page, you will have to set up again on current page!**"
            ],
            label=f"Select page {_pnum}",
            description=f"Data will be saved after you select IP",
            custom_view=ui_view,
            author_check=True,
        )
        _pages.append(_pgroup)
        _uis.append(ui_view)
    _confirm = Confirm(ctx.author, 180)
    _paginator = pages.Paginator(pages=_pages, show_menu=True, author_check=True)
    await _paginator.respond(ctx.interaction, ephemeral=False)
    msg = await ctx.respond(
        "Press Confirm to delete selected map query from guild",
        view=_confirm,
        ephemeral=True,
    )
    for _ui_select in _uis:
        _ui_select.set_msg(msg)
    await _confirm.wait()
    _selected_ip = list(chain.from_iterable([v for v in _selected_val.values()]))
    if _confirm.cancel or len(_selected_val) <= 0:
        await ctx.respond("Option canceled", ephemeral=True)
        embeds.title = "No query were deleted"
        embeds.description = None
    else:
        try:
            for ip in _selected_ip:
                print(await gettracking(ctx.guild.id, ip))
        except Exception as e:
            raise e
        else:
            await ctx.respond(
                content=f"Succesfully deleted from map query {_selected_ip}",
                ephemeral=True,
            )
            embeds.title = "Deleted query"

    embeds.color = ctx.author.color
    embeds.set_author(name=ctx.author)
    await _paginator.disable(include_custom=True, page=embeds)
    _confirm.stop()
    _paginator.stop()
