import discord
from discord.ext import commands
from discord import app_commands
import random

class DiceCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="roll_d4", description="Roll a 4-sided die")
    async def roll_d4(self, interaction: discord.Interaction):
        result = random.randint(1, 4)
        await interaction.response.send_message(f'🎲 You rolled a d4: **{result}**')

    @app_commands.command(name="roll_d5", description="Roll a 5-sided die")
    async def roll_d5(self, interaction: discord.Interaction):
        result = random.randint(1, 5)
        await interaction.response.send_message(f'🎲 You rolled a d5: **{result}**')

    @app_commands.command(name="roll_d6", description="Roll a 6-sided die")
    async def roll_d6(self, interaction: discord.Interaction):
        result = random.randint(1, 6)
        await interaction.response.send_message(f'🎲 You rolled a d6: **{result}**')

    @app_commands.command(name="roll_d12", description="Roll a 12-sided die")
    async def roll_d12(self, interaction: discord.Interaction):
        result = random.randint(1, 12)
        await interaction.response.send_message(f'🎲 You rolled a d12: **{result}**')

    @app_commands.command(name="roll_d20", description="Roll a 20-sided die")
    async def roll_d20(self, interaction: discord.Interaction):
        result = random.randint(1, 20)
        await interaction.response.send_message(f'🎲 You rolled a d20: **{result}**')

    @app_commands.command(name="roll_d86", description="Roll a 86-sided die")
    async def roll_d86(self, interaction: discord.Interaction):
        result = random.randint(1, 86)
        await interaction.response.send_message(f'🎲 You rolled a d86: **{result}**')

async def setup(bot):
    await bot.add_cog(DiceCog(bot))
