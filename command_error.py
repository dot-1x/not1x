from inspect import trace
import secrets
import traceback
import typing as t
import discord
import not1x

from datetime import datetime
from discord.ext.commands.errors import *
from discord.ext import commands, bridge
from discord.errors import *
from discord import Embed, Colour, TextChannel
from logs import setlog
from enums import *
from aiomysql import OperationalError

_logger = setlog(__name__)


class StdErrChannel(UserInputError):
    def __init__(self, message=None, *args):
        super().__init__("Cannot send message in std_err channel")


class CommandInputError(UserInputError):
    def __init__(self, message=None, *args):
        super().__init__(message=message)


async def CheckError(
    ctx: t.Optional[discord.ApplicationContext | commands.Context],
    error: t.Optional[commands.CommandError | discord.ApplicationCommandError],
):
    _error = "An error occured."
    _base_error = None
    _invoke = ctx.invoked_with if isinstance(ctx, bridge.BridgeExtContext) else ctx.command
    embeds = Embed()

    if isinstance(error, CommandNotFound):
        _error = str(error)
    elif isinstance(error, ValueError):
        _error = str(error)
    elif isinstance(error, (NotOwner, MissingPermissions)):
        _error = "You do not have access to this command."
    elif isinstance(error, Forbidden):
        _error = "I dont have an access to do as you wish!"
    elif isinstance(error, NotOwner):
        _error = "You do not have access to this command."
    elif isinstance(error, CheckFailure):
        _error = f'Failed to check for command "{_invoke}"'
    elif isinstance(error, (RoleNotFound, MemberNotFound, UserNotFound)):
        _error = str(error)
    elif isinstance(error, CommandOnCooldown):
        _error = str(error)
    elif isinstance(error, CommandInputError):
        _error = str(error)
    elif isinstance(error, OperationalError):
        _error = f"Failed to connect to database!"
    elif isinstance(error, (MissingRequiredArgument, BadArgument, BadUnionArgument)):
        cmd_used = ctx.command
        _error = cmd_used.description
        embeds.description = (
            f'**Usage of "{_invoke}" command:**\n {cmd_used.usage}' if cmd_used.usage is not None else str(error)
        )
    elif isinstance(error, (CommandInvokeError, ApplicationCommandInvokeError)):
        _base_error = error.original
        await CheckError(ctx, _base_error)
        return

    _err_id = secrets.randbits(64)
    embeds.title = _error
    embeds.set_footer(text=f"Error ID: {_err_id}")
    embeds.colour = Colour.red()

    try:
        await ctx.reply(embed=embeds)
    except Exception as e:
        _logger.error(f"Failed to reply to user with error {e}")

    bot = ctx.bot or not1x.Bot
    std_err: TextChannel = bot.get_channel(Data.STD_ERR_CHANNEL.value)
    _err_msg = Embed()
    _err_msg.title = "Command error invoked"
    _err_msg.set_author(name=ctx.author)
    fields = [
        ("Error:", f"```{error}```", False),
        ("User:", f"```{ctx.author}```", False),
        ("Invoked with:", f"```{_invoke}```", False),
        ("Guild name:", f"```{ctx.guild.name}```", False),
        ("Guild id:", f"```{ctx.guild.id}```", False),
        ("Channel name:", f"```{ctx.channel.name}```", False),
        ("Channel id:", f"```{ctx.channel.id}```", False),
        ("Error id: ", f"```{_err_id}```", False),
    ]

    for _name, _value, _inline in fields:
        _err_msg.add_field(name=_name, value=_value, inline=_inline)

    _err_msg.timestamp = datetime.utcnow()

    _logger.warning(error)

    with open("logs/traceback.log", "a") as f:
        f.write(
            str(datetime.utcnow()) + "\n" + f"ID: {_err_id}\n" + str(error.with_traceback(error.__traceback__)) + "\n"
        )
        traceback.print_tb(error.__traceback__, file=f)

    await std_err.send(embed=_err_msg)
