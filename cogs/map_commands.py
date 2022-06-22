import json
import re
import discord
import ui_utils
import not1x

from datetime import datetime
from multiprocessing import Process
from ipaddress import ip_address
from db import (
    getchannel,
    getnotify,
    gettracking,
    inserttracking,
    updatechannel,
)
from enums import *
from discord.ext import commands, pages, tasks
from logs import setlog
from map_list.findmap import updatemap, aupdatemap
from source_query import GetServer
from tasks.map_task import ServerTask
from discord.commands import SlashCommandGroup, slash_command

_logger = setlog(__name__)


class MapCommands(commands.Cog):
    def __init__(self, bot: not1x.Bot) -> None:
        self.bot = bot

    server = SlashCommandGroup("server", "Commands for source server")
    notify = SlashCommandGroup("notify", "Group for notify command")

    @server.command(description="Checks about source server info")
    @discord.option(name="ip", type=str, description="A server ip address")
    @discord.option(name="port", type=int, description="A server port")
    async def info(self, ctx: discord.ApplicationContext, ip: str, port: int):
        await ctx.defer()
        ip = ip_address(ip)
        port = port
        _server = await GetServer(ip, port)

        class ButtonView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=30)

            @discord.ui.button(label="Player List", style=discord.ButtonStyle.secondary)
            async def sendplayer(self, _button: discord.ui.Button, _interaction: discord.Interaction):

                _pl = await _server.players()
                if not _pl:
                    await _interaction.response.send_message("Server doesn't respond", ephemeral=True)
                    return

                _logger.info(f"Sending player list {_server.ip_port} to {_interaction.user}")

                _players = "\n".join(sorted([p.name for p in _pl]))

                try:
                    await _interaction.user.send(
                        content=f"**{_server.name}** ({len(_pl)}/{_server.maxplayers})\n```{_players}```"
                    )
                    await _interaction.response.send_message("Player list sent to pm", ephemeral=True)
                except discord.Forbidden:
                    await _interaction.response.send_message(
                        "i cant send the players on private message", ephemeral=True
                    )
                except Exception as e:
                    _logger.warning(e)

        _view = ButtonView()
        _server.set_author(name=ctx.author, icon_url=ctx.author.avatar.url)

        await ctx.respond(embed=_server, view=_view)
        await _view.wait()
        _view.disable_all_items()
        try:
            await ctx.edit(embed=_server, view=_view)
        except:
            _logger.warning("Couldn't edit message")

    @server.command(description="Get this guild map tracking list")
    async def list(self, ctx: discord.ApplicationContext):

        notify_list = await gettracking(ctx.guild.id)
        if not len(notify_list):
            await ctx.respond("This guild currently has no server query")
            return
        icon = ctx.guild.icon
        embed = discord.Embed()
        embed.set_author(name=ctx.guild.name, icon_url=icon.url if icon else embed.Empty)
        embed.title = "Server query list"
        embed.description = "\n".join(notify_list)

        await ctx.respond(embed=embed)

    @server.command(description="upate guild tracking channel")
    @discord.option(
        name="channel",
        type=discord.TextChannel,
        description="Specify a channel, fill this to update channel tracking, one channel is for all tracking",
        required=True,
    )
    @commands.has_permissions(manage_guild=True)
    async def channel(self, ctx: discord.ApplicationContext, channel: discord.TextChannel):
        await ctx.respond(f"Successfully updated channel to <#{channel.id}>")
        await updatechannel(ctx.guild.id, channel.id)

    @server.command(description="add a server to map tracking")
    @discord.option(name="ip", type=str, description="Server ip address")
    @discord.option(name="port", type=int, description="Server port")
    @discord.option(
        name="channel",
        type=discord.TextChannel,
        description="Specify a channel, fill this to update channel tracking, one channel is for all tracking",
        required=False,
    )
    @commands.has_permissions(manage_guild=True)
    async def add(
        self,
        ctx: discord.ApplicationContext,
        ip: str,
        port: int,
        channel: discord.TextChannel = None,
    ):

        await ctx.defer()

        ip = ip_address(ip)
        port = int(port)
        ipport = f"{str(ip)}:{port}"
        _tracking = await gettracking(ctx.guild.id)
        _channel = self.bot.get_channel(await getchannel(ctx.guild.id))

        if channel:
            await updatechannel(ctx.guild.id, channel.id)
            await ctx.send(f"Successfully updated channel to <#{channel.id}>")
            _channel = self.bot.get_channel(channel.id)

        if not _channel:
            await ctx.respond("Please specify a tracking channel first")
            return

        serverstatus = await GetServer(ip=ip, port=port)

        if ipport in _tracking:
            await ctx.respond("Given server ip is already on map tracking")
            return

        if not serverstatus.status:
            await ctx.respond("given server ip did not respond please try again later")
            return

        _sv_list = self.bot.config["serverquery"]

        if ipport not in _sv_list:
            _v = ui_utils.PlayerListV(bot=self.bot, ip=str(ip), port=port)
            self.bot.persview[ipport] = _v

            loop = ServerTask(
                bot=self.bot,
                name=ipport,
                ipport=ipport,
                view=_v,
            )

            _sv_list.append(ipport)
            with open(self.bot.config["path"], "w") as w:
                json.dump(self.bot.config, w)
            _logger.info(f"Added new server '{ipport}' to map task")

        await ctx.respond(f"Successfully added **{serverstatus.name}** to map tracking")
        await inserttracking(ctx.guild.id, _channel.id, ipport, 0)

    @server.command(description="Delete an existed task query on guild")
    @commands.has_permissions(manage_guild=True)
    async def delete(self, ctx: discord.ApplicationContext):
        notify_list = await gettracking(ctx.guild.id)

        if not len(notify_list):
            await ctx.respond("This guild currently has no server query")
            return
        opt = [discord.SelectOption(label=x, value=x) for x in notify_list]

        await ui_utils.view_select_server_query(ctx, opt)

    @slash_command(description="Update map list (bot owner only)")
    @commands.cooldown(1, 3600, commands.BucketType.user)
    async def update_map(self, ctx: discord.ApplicationContext):
        if ctx.author.id not in self.bot.owner_ids:
            raise commands.NotOwner(f"{ctx.author.name} invoking updatemap")

        starttime = datetime.now()

        await ctx.respond("please wait till i finish updating map list...")

        # self.bot.loop.run_until_complete(await aupdatemap())
        p = Process(target=updatemap, name="Updatemap")
        p.start()

        @tasks.loop(seconds=1)
        async def checkprocess():
            if p.is_alive():
                pass
            else:
                endtime = datetime.now()
                await ctx.edit(content=f"Succcessfully updated map list in {endtime-starttime}")
                checkprocess.stop()

        checkprocess.start()

    @notify.command(description="Notify a map when its played (ZE only)")
    async def map(
        self,
        ctx: discord.ApplicationContext,
        *,
        map: discord.Option(str, description="map name to notify, auto regex, divided by space"),
    ):
        await ctx.defer()

        founded_map = []
        invalid_map = []
        for _map in map.split(" "):
            _map: str = _map.lower()
            if len(_map) < 5:
                continue
            with open("map_list/maplist.txt") as maps:
                _maps = maps.read()
                if not re.search(_map, _maps):
                    invalid_map.append(_map)
                    continue
                founded_map.extend([m for m in _maps.split("\n") if re.search(_map, m) and m not in founded_map])

        embeds = discord.Embed()

        if len(invalid_map) > 0:
            embeds.title = "Invalid Maps:"
            embeds.description = f"\n".join(invalid_map)
            await ctx.respond(embed=embeds, delete_after=10)

        if len(founded_map) < 1:
            await ctx.respond("None map found!")
            return

        user_notified_maps = await getnotify(ctx.author.id)
        _options = [discord.SelectOption(label=a, value=a) for a in founded_map if a not in user_notified_maps]
        await ui_utils.view_select_map(ctx, _options, True)

    @notify.command(name="list", description="Get your notification list")
    async def notify_list(self, ctx: discord.ApplicationContext):
        await ctx.defer()
        user_notify = await getnotify(ctx.author.id)
        if len(user_notify) < 1:
            await ctx.respond("Currently no notification!")
            return
        _pages = [
            [
                discord.Embed(
                    title="Map Notification",
                    description="\n".join(user_notify[x : x + 25]),
                    color=ctx.author.colour,
                ).set_author(
                    name=ctx.author.name,
                    icon_url=ctx.author.display_avatar.url if ctx.author.display_avatar else discord.Embed.Empty,
                )
            ]
            for x in range(0, len(user_notify), 25)
        ]

        paginator = pages.Paginator(_pages, menu_placeholder=f"{ctx.author.name} Notification list")
        await paginator.respond(ctx.interaction)

    @notify.command(name="edit", description="Edit or delete your notification list")
    async def notify_edit(self, ctx: discord.ApplicationContext):
        await ctx.defer()
        user_notify = await getnotify(ctx.author.id)
        if len(user_notify) < 1:
            await ctx.respond("Currently no notification!")
            return
        _options = [discord.SelectOption(label=a, value=a) for a in user_notify]
        await ui_utils.view_select_map(ctx, _options, False)


def setup(bot):
    bot.add_cog(MapCommands(bot))
