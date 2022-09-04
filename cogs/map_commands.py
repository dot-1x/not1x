import json
import re
from datetime import datetime
from ipaddress import ip_address
from itertools import chain
from multiprocessing import Process

import discord
from discord.commands import SlashCommandGroup, slash_command
from discord.ext import commands, pages, tasks

import not1x
import ui_utils
from enums import *
from logs import setlog
from map_list.findmap import updatemap
from source_query import GetServer
from tasks.map_task import ServerTask
from utils import addhelp, most_color

_logger = setlog(__name__)


class MapCommands(commands.Cog):
    def __init__(self, bot: not1x.Bot) -> None:
        self.bot = bot

    server = SlashCommandGroup("server", "Commands for source server")
    notify = SlashCommandGroup("notify", "Group for notify command")
    mapgroup = notify.create_subgroup("map", "Notify a map")

    @server.command(description="Checks about source server info", usage="no usage!")
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

        notify_list = await self.bot.db.gettracking(ctx.guild.id)
        if not len(notify_list):
            await ctx.respond("This guild currently has no server query")
            return
        icon = ctx.guild.icon
        embed = discord.Embed()
        embed.set_author(name=ctx.guild.name, icon_url=icon.url if icon else embed.Empty)
        embed.title = "Server query list"
        embed.description = "\n".join(notify_list)

        embed.color = await most_color(ctx.guild.icon)

        await ctx.respond(embed=embed)

    @server.command(description="upate guild tracking channel")
    @discord.option(
        name="channel",
        type=discord.TextChannel,
        description="Specify a channel, fill this to update channel tracking, one channel is for all tracking",
        required=True,
    )
    @commands.has_permissions(manage_guild=True)
    @addhelp("set the tracking channel, if guild haven't set any yet, it'll add it, else update it")
    async def channel(self, ctx: discord.ApplicationContext, channel: discord.TextChannel):
        try:
            await self.bot.db.updatechannel(ctx.guild.id, channel.id)
        except Exception as e:
            raise e
        else:
            await ctx.respond(f"Successfully updated channel to <#{channel.id}>")

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
    @addhelp(
        "add source server to track on current guild\nusage:\n<ip>: must be filled with ipv4 address format, you cannot fill with dns or any invalid ipv4 format\n<port>: server port\n[channel]: select the channel you want to add the tracking to, one channel is for all tracking, if you havent set a channel yet, this field is **REQUIRED**"
    )
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
        _tracking = await self.bot.db.gettracking(ctx.guild.id)
        _channel = self.bot.get_channel(await self.bot.db.getchannel(ctx.guild.id))

        if channel:
            await self.bot.db.updatechannel(ctx.guild.id, channel.id)
            await ctx.send(f"Successfully updated channel to <#{channel.id}>")
            _channel = self.bot.get_channel(channel.id)

        if not _channel:
            return await ctx.respond("Please specify a tracking channel first")

        serverstatus = await GetServer(ip=ip, port=port)

        if ipport in _tracking:
            return await ctx.respond("Given server ip is already on map tracking")

        if not serverstatus.status:
            return await ctx.respond("given server ip did not respond please try again later")

        _sv_list = self.bot.config["serverquery"]

        if ipport not in _sv_list:
            _v = ui_utils.PlayerListV(bot=self.bot, ip=str(ip), port=port)
            self.bot.persview[ipport] = _v
            self.bot.add_view(_v)

            sv = ServerTask(
                bot=self.bot,
                name=ipport,
                ipport=ipport,
                view=_v,
            )

            _sv_list.append(ipport)
            with open(self.bot.config["path"], "w") as w:
                json.dump(self.bot.config, w)
            self.bot.server_task[ipport] = tasks.Loop(
                sv.servercheck,
                60,
                discord.MISSING,
                discord.MISSING,
                time=discord.MISSING,
                count=None,
                loop=self.bot.loop,
                reconnect=True,
            )
            self.bot.server_task[ipport].start()
            self.bot.server_task[ipport].get_task().set_name(ipport)
            _logger.info(f"Added new server '{ipport}' to map task")

        await ctx.respond(f"Successfully added **{serverstatus.name}** to map tracking")
        await self.bot.db.inserttracking(ctx.guild.id, _channel.id, ipport, 0)

    @server.command(description="Delete an existed task query on guild")
    @commands.has_permissions(manage_guild=True)
    @addhelp(
        "Delete existed server query from guild, select the ip from the page to delete from current server query list and press CONFIRM"
    )
    async def delete(self, ctx: discord.ApplicationContext):
        notify_list = await self.bot.db.gettracking(ctx.guild.id)

        if not len(notify_list):
            return await ctx.respond("This guild currently has no server query")
        opt = [discord.SelectOption(label=x, value=x) for x in notify_list]
        await ui_utils.select_ip(ctx, opt)

    @slash_command(description="Update map list", guild_ids=[620983321677004800])
    @commands.cooldown(1, 3600, commands.BucketType.user)
    @addhelp("Bot Owner only commands")
    async def update_map(self, ctx: discord.ApplicationContext):
        if ctx.author.id not in self.bot.owner_ids:
            raise commands.NotOwner(f"{ctx.author.name} invoking updatemap")
        await ctx.respond("please wait till i finish updating map list...")
        await updatemap()

    @mapgroup.command(name="find", description="notify a map by selecting map on current db")
    @addhelp(
        "Find a map from current map database and add it to your notification list, usage:\n /notify map find ze_deadcore ze_ffxii\nall founded map will be showen on the page, select the map you want to notify and press CONFIRM"
    )
    async def map_find(
        self,
        ctx: discord.ApplicationContext,
        *,
        map: discord.Option(str, description="map name to notify, auto find, divided by space, length min 5"),
    ):
        await ctx.defer()

        founded_map = []
        invalid_map = []
        for _map in map.split(" "):
            _map: str = _map.lower()
            if len(_map) < 5:
                invalid_map.append(_map)
                continue
            with open("map_list/maplist.txt") as maps:
                _maps = maps.read()
                if not re.search(_map, _maps):
                    invalid_map.append(_map)
                    continue
                founded_map.extend([m for m in _maps.split("\n") if re.search(_map, m) and m not in founded_map])

        embeds = discord.Embed()

        if len(founded_map) < 1:
            return await ctx.respond("None map found!")

        user_notified_maps = [m async for m in self.bot.db.getnotify(ctx.author.id)]
        if len(user_notified_maps) > 300:
            return await ctx.respond("**Your current notification list have more than 300!**, consider using *regex* notification")
        opt = [discord.SelectOption(label=a, value=a) for a in founded_map if a not in user_notified_maps]
        if len(opt) > 250:
            await ctx.respond("More than 250 maps found!")
            return
        if len(invalid_map) > 0:
            embeds.title = "Invalid Maps:"
            embeds.description = f"\n".join(invalid_map)
            await ctx.send(embed=embeds, delete_after=10)
        await ui_utils.select_map(ctx, opt)

    @mapgroup.command(name="re", description="Notify a map using regex, map with founded string will be notified")
    @addhelp(
        "Notify a map by using regex, founded map will be notified, eg: /notify map re ze_ (all map containing with 'ze_' will be notified)"
    )
    async def map_re(
        self,
        ctx: discord.ApplicationContext,
        pattern: discord.Option(str, description="string pattern to notify"),
    ):
        await ctx.defer()
        
        user_notified_maps = [m async for m in self.bot.db.getnotify(ctx.author.id)]
        if len(user_notified_maps) > 300:
            return await ctx.respond("**Your current notification list have more than 300!**, consider using *regex* notification")
            
        pattern: str = pattern.strip()
        if re.search("\s", string=pattern):
            return await ctx.respond("pattern must not contain any whitespace")
        await self.bot.db.insertnotify(ctx.author.id, ctx.author, [pattern.lower()])
        await ctx.respond(f"String pattern: **{pattern}** added to notification")

    @notify.command(name="list", description="Get your notification list")
    async def notify_list(self, ctx: discord.ApplicationContext):
        await ctx.defer()
        user_notify = [m async for m in self.bot.db.getnotify(ctx.author.id)]
        if len(user_notify) < 1:
            return await ctx.respond("Currently no notification!")
        _pages = [
            [
                discord.Embed(
                    title="Map Notification",
                    description="\n".join(user_notify[x : x + 25]),
                    color=await most_color(ctx.author.avatar),
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
    @addhelp("Edit your notification, select the map from map page, and press CONFIRM to delete your notification")
    async def notify_edit(self, ctx: discord.ApplicationContext):
        await ctx.defer()
        user_notify = [m async for m in self.bot.db.getnotify(ctx.author.id)]
        if len(user_notify) < 1:
            return await ctx.respond("Currently no notification!")

        opt = [discord.SelectOption(label=a, value=a) for a in user_notify]
        await ui_utils.select_map(ctx, opt, edit=True)


def setup(bot):
    bot.add_cog(MapCommands(bot))
