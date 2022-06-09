import asyncio
import discord
import typing as t
import not1x

from enums import Data
from discord.ext import commands, bridge
from command_error import CommandInputError
from logs import setlog
from utils import restart_map_loop


_logger = setlog(__name__)


class AdminCommands(commands.Cog):
    def __init__(self, bot: not1x.Bot) -> None:
        self.bot = bot

    @bridge.bridge_command(name="clear", description="Clear message on current channel")
    @commands.has_permissions(manage_messages=True)
    @discord.option(name="amount", type=int, description="Amount of message to delete")
    @discord.option(
        name="Target",
        type=discord.Member,
        description="Member target to delete the message",
        required=False,
    )
    async def clear(
        self,
        ctx: bridge.BridgeContext,
        amount: int,
        target: t.Optional[discord.Member] = None,
    ):
        channel = ctx.channel
        max_limit = 100
        if amount > max_limit:
            raise CommandInputError(f"Amount must not exceed max limit ({max_limit})")

        def check(msg: discord.Message):
            return (True if target is None else target == msg.author) and msg != ctx.message

        deleted_msg = await channel.purge(limit=amount, check=check)
        await asyncio.sleep(1)
        await ctx.reply(
            content=f"Successfully deleted {len(deleted_msg)} message(s) in: {channel.mention}",
            delete_after=5,
        )

    @discord.slash_command(guild_ids=[Data.OWNER_GUILD.value])
    async def restart_loop_map(self, ctx: discord.ApplicationContext):
        loops = [l.get_name() for l in asyncio.all_tasks() if l.get_name() in self.bot.loop_maptsk]
        stopped_loop = [l for l in self.bot.loop_maptsk.keys() if l not in loops]

        lembed = discord.Embed(title="Running Loop", color=discord.Colour.blurple())
        lembed.description = "\n".join(loops)

        sembed = discord.Embed(title="Stopped Loop", color=discord.Colour.blurple())
        sembed.description = "\n".join(stopped_loop)

        await ctx.respond(embeds=[lembed, sembed])
        await restart_map_loop(self.bot)


def setup(bot: commands.Bot):
    bot.add_cog(AdminCommands(bot))
