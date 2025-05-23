import discord
from discord.ext import commands
from discord import app_commands
import random

class DiceCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="roll", description="Roll a die with any number of sides (e.g. 4, 5, 6, 12, 20, 86)")
    @app_commands.describe(sides="Number of sides on the die (must be at least 2)")
    async def roll(self, interaction: discord.Interaction, sides: int):
        if sides < 2:
            await interaction.response.send_message("Please enter a number greater than 1 for the sides.", ephemeral=True)
            return
        result = random.randint(1, sides)
        await interaction.response.send_message(f'🎲 You rolled a d{sides}: **{result}**')

async def setup(bot):
    await bot.add_cog(DiceCog(bot))
