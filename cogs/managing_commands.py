import discord
import typing as t

from discord.ext import commands, bridge
from command_error import command_input_error
from logs import setlog


_logger = setlog(__name__)

class AdminCommands(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        _logger.info("Extension loaded")

    @bridge.bridge_command(
        name="clear",
        description="Clear message on current channel"
    )
    @commands.has_permissions(manage_messages=True)
    @discord.option(
        name="amount",
        type=int,
        description="Amount of message to delete"
    )
    @discord.option(
        name="Target",
        type=discord.Member,
        description="Member target to delete the message",
        required=False
    )
    async def clear(self, ctx: bridge.BridgeContext, amount: int, target: t.Optional[discord.Member] = None):
        channel = ctx.channel
        max_limit = 300
        if amount > max_limit:
            raise command_input_error("Amount must not exceed max limit (300)")

        if isinstance(ctx, bridge.BridgeApplicationContext):
            m = await ctx.respond("Deleting messages...", ephemeral=True)
            m = await m.original_message()
        else:
            m = await ctx.reply("Deleting messages...")
        deleted_msg = 0
        async for msg in channel.history(limit=max_limit):
            if deleted_msg >= amount:
                break
            if ctx.message == msg or msg == m:
                continue
            if msg.author == target and target is not None:
                await msg.delete()
            else:
                await msg.delete()
            deleted_msg += 1
        await m.edit(f"Successfully deleted {deleted_msg} message(s) in: {channel.mention}", delete_after = 5)


def setup(bot: commands.Bot):
    bot.add_cog(AdminCommands(bot))
