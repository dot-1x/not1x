import typing as t

import discord
from discord.ext import bridge, commands

from not1x import Bot


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
            return
        if len(exts) > 0:
            for ext_ in exts:
                self.bot.reload_extension(ext_)
        await ctx.send(f"Extension Loaded: {self.bot.extensions[0]}")


def setup(bot: Bot):
    bot.add_cog(AdminCog(bot))
