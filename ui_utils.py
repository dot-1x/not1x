import discord
import typing as t

from logs import setlog
from discord.ext import pages, commands
from enums import *
from itertools import chain
from db import *
from source_query import GetServer
from ipaddress import ip_address

_logger = setlog(__name__)


class PlayerListV(discord.ui.View):
    def __init__(self, bot: commands.Bot, ip: str, port: int):

        self.ip = ip_address(ip)
        self.port = port
        self.bot = bot

        super().__init__(timeout=None)
        btn = discord.ui.Button(
            custom_id=f"{ip}:{port}",
            style=discord.ButtonStyle.secondary,
            label="Player List",
        )
        btn.callback = self.sendplayer
        self.add_item(btn)

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
