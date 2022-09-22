import typing as t

import discord
from discord.ext import bridge, commands

from enums import *
from logs import setlog
from not1x import Bot
from utils import addhelp, generate_help_embed, help_command, most_color

_logger = setlog(__name__)


class AdminCog(commands.Cog):
    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    @bridge.bridge_command(
        desciprtion="reload any extension",
        usage="( reload_ext ): ext name, empty for all loaded ext",
        guild_ids=[620983321677004800],
    )
    @discord.option(name="exts", type=str, description="extension name to reload", required=False)
    @commands.cooldown(1, 15, commands.BucketType.user)
    @addhelp("Bot owner only command")
    async def reload_ext(
        self, ctx: t.Optional[bridge.BridgeApplicationContext | bridge.BridgeExtContext], *, exts: str = None
    ):
        await ctx.reply("Reloading extensions")
        if ctx.author.id not in ctx.bot.owner_ids:
            raise commands.NotOwner("You Do not have permission to use this commands")
        if not exts:
            self.bot.reload_extension()
        elif len(exts.split(" ")) > 0:
            for ext_ in exts.split(" "):
                self.bot.reload_extension(ext_)
        await ctx.send(f"Extension Loaded: {list(self.bot.extensions.keys())}")

    @commands.slash_command(description="Show list of available command!", usage="dsjakljdlw")
    @discord.option(name="command", description="find specific command help", type=str, required=False)
    @addhelp("Show help of current available command, usage: /help [command]")
    async def help(self, ctx: bridge.BridgeApplicationContext, command: str = None):
        await ctx.defer()
        cmds = [generate_help_embed(c) for c in self.bot.application_commands]
        em = discord.Embed(title="List Of Available Command!", color=await most_color(ctx.author.avatar))
        flattened_cmd: t.List[discord.SlashCommand] = []

        def _flat(li):
            for c in li:
                if type(c) == list:
                    _flat(c)
                else:
                    flattened_cmd.append(c)

        _flat(cmds)
        if command:
            cmd = [c for c in flattened_cmd if c.qualified_name == command]
            if not len(cmd):
                return await ctx.respond(f"No command named **{command}** found!")
            em.title = "Specific command help"
            em.description = "**<...>**: Required parameter\n**[...]**: Optional parameter"
            em.add_field(
                name=f"{command} command usage",
                value=help_command.get(cmd[0].callback, "No help provided!"),
                inline=False,
            )
            return await ctx.respond(embed=em)
        em.description = "**Use /help [command] to search up specific command help**\nMap notification is *limited to 300* due to discord view limitation"
        for c in flattened_cmd:
            em.add_field(name=c.qualified_name, value=c.description, inline=True)
        await ctx.respond(embed=em)


def setup(bot: Bot):
    bot.add_cog(AdminCog(bot))
