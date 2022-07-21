from random import randint
from typing import Counter

import discord
from discord.commands import slash_command
from discord.ext import commands

from logs import setlog
from ui_utils import Confirm

_logger = setlog(__name__)


class FunCommands(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @slash_command(
        name="tic_tac_toe",
        description="play a tic tac toe game with friends or challenge the bot!",
    )
    @discord.option(
        name="opponent",
        type=discord.Member,
        description="Select an opponent to play with",
        required=False,
    )
    async def ttt(self, ctx: discord.ApplicationContext, opponent: discord.Member = None):
        opponent = opponent or ctx.bot.user
        if opponent == ctx.author:
            await ctx.respond(content="You cant face yourself!", ephemeral=True)
            return

        class tttbutton(discord.ui.Button):
            def __init__(self, label: str, custom_id: str, row: int):
                self._col = custom_id.split(":")[1]
                self._rows = custom_id.split(":")[0]
                self._cid = custom_id
                super().__init__(style=discord.ButtonStyle.grey, label=label, row=row)

            async def callback(self, interaction: discord.Interaction):
                view: tttview = self.view
                if interaction.user != view.turn and view.turn != ctx.bot.user:
                    await interaction.response.send_message("Not your turn!", ephemeral=True)
                    return

                if view.turn != ctx.bot.user:
                    try:
                        await interaction.response.send_message(f"You have choosen: {self._cid}", ephemeral=True)
                    except:
                        return

                self.disabled = True
                self.label = view.getstate()
                self.style = discord.ButtonStyle.green if self.label == "X" else discord.ButtonStyle.red

                view.table[self._rows][self._col] = view.turn

                if view.getwinner():

                    view.disable_all_items()
                    embeds = interaction.message.embeds[0]
                    embeds.description = f"{view.turn.mention} won the game!"
                    await interaction.message.edit(embed=embeds, view=view)
                    view.stop()
                    try:
                        await interaction.response.send_message(
                            content="Congrats you have won the game!"
                            if view.turn == interaction.user
                            else f"<@{view.turn.id}> won the game!",
                            ephemeral=True,
                        )
                    except:
                        await interaction.followup.send(
                            content="Congrats you have won the game!"
                            if view.turn == interaction.user
                            else f"<@{view.turn.id}> won the game!",
                            ephemeral=True,
                        )
                    return
                else:
                    if view.tie:
                        embeds = interaction.message.embeds[0]
                        embeds.description = f"Game tie!"
                        await interaction.message.edit(embed=embeds, view=view)
                        view.stop()
                        return
                await interaction.message.edit(view=view)
                await view.switchturn(interaction)

        class tttview(discord.ui.View):
            def __init__(self, bot: commands.Bot):
                super().__init__(timeout=180)
                self.turn = ctx.author

                self.p2: discord.Member = opponent
                self.p1 = ctx.author
                self.tie = False

                self.state = "O"
                self.table = {}

                for x in range(3):
                    row = f"row-{x+1}"
                    self.table[row] = {}
                    for y in range(3):
                        col = f"col-{y+1}"
                        self.table[row][col] = None
                        self.add_item(tttbutton(label="-", custom_id=row + ":" + col, row=x))

            async def switchturn(self, _interaction: discord.Interaction):
                self.turn = self.p2 if self.turn != self.p2 else self.p1
                child = []

                for c in self.children:
                    if not c.disabled:
                        child.append(c)

                if len(child) == 0:
                    return

                if self.turn == ctx.bot.user:
                    await child[randint(0, len(child) - 1)].callback(_interaction)

            def getstate(self) -> str:
                self.state = "O" if self.state == "X" else "X"
                return self.state

            def getwinner(self) -> bool:
                for x in range(1, 4):
                    row = []
                    col = []
                    for y in range(1, 4):
                        row.append(self.table[f"row-{x}"][f"col-{y}"])
                        col.append(self.table[f"row-{y}"][f"col-{x}"])
                    if self.turn in Counter(row):
                        if Counter(row)[self.turn] >= 3:
                            return True
                    if self.turn in Counter(col):
                        if Counter(col)[self.turn] >= 3:
                            return True

                diag1 = [
                    self.table[f"row-1"][f"col-1"],
                    self.table[f"row-2"][f"col-2"],
                    self.table[f"row-3"][f"col-3"],
                ]
                diag2 = [
                    self.table[f"row-1"][f"col-3"],
                    self.table[f"row-2"][f"col-2"],
                    self.table[f"row-3"][f"col-1"],
                ]

                if self.turn in Counter(diag1):
                    if Counter(diag1)[self.turn] >= 3:
                        return True
                if self.turn in Counter(diag2):
                    if Counter(diag2)[self.turn] >= 3:
                        return True

                self.tie = True

                for c in self.children:
                    if not c.disabled:
                        self.tie = False

                return False

        embeds = discord.Embed()
        embeds.set_author(name=f"Tic Tac Toe")
        embeds.set_footer(text=f"requested by: {ctx.author}")

        _v = tttview(ctx.bot)

        if opponent != ctx.bot.user:
            _confirm = Confirm(opponent, 30)
            embeds.description = f"Waiting {opponent.mention} confirmation..."
            await ctx.respond(embed=embeds, view=_confirm)
            await _confirm.wait()
            if _confirm.cancel:
                embeds.description = "Opponent have canceled the request!"
                await ctx.edit(embed=embeds, view=None)
            else:
                embeds.description = f"Tic Tac Toe game {ctx.author.mention} vs {opponent.mention}"
                await ctx.edit(embed=embeds, view=_v)
        else:
            embeds.description = f"Tic Tac Toe game {ctx.author.mention} vs {opponent.mention}"
            await ctx.respond(view=_v, embed=embeds)


def setup(bot: commands.Bot):
    bot.add_cog(FunCommands(bot))
