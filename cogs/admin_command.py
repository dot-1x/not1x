import typing as t

import discord
from discord.ext import bridge, commands

from enums import *
from logs import setlog
from not1x import Bot
from utils import generate_help_embed, most_color

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
    async def reload_ext(
        self, ctx: t.Optional[bridge.BridgeApplicationContext | bridge.BridgeExtContext], *, exts=None
    ):
        await ctx.reply("Reloading extensions")
        if ctx.author.id not in ctx.bot.owner_ids:
            raise commands.NotOwner("You Do not have permission to use this commands")
        if not exts:
            self.bot.reload_extension()
        elif len(exts) > 0:
            for ext_ in exts:
                self.bot.reload_extension(ext_)
        await ctx.send(f"Extension Loaded: {list(self.bot.extensions.keys())}")

    @commands.slash_command(description="Show list of available command!")
    async def help(self, ctx: bridge.BridgeApplicationContext):
        await ctx.defer()
        cmds = [generate_help_embed(c) for c in self.bot.application_commands]
        em = discord.Embed(title="List Of Available Command!", color=await most_color(ctx.author.avatar))
        flattened_cmd: t.List[discord.EmbedField] = []

        def _flat(li):
            for c in li:
                if type(c) == list:
                    _flat(c)
                else:
                    flattened_cmd.append(c)

        _flat(cmds)
        for c in flattened_cmd:
            em.append_field(c)
        await ctx.respond(embed=em)


def setup(bot: Bot):
    bot.add_cog(AdminCog(bot))
