import discord
from discord.ext import commands
from discord import app_commands

class ReplyCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Example: map user IDs to custom replies
        self.user_replies = {
            # Replace/add user IDs and messages as needed
            123456789012345678: "Hello, special user!",
            987654321098765432: "Hey there, VIP!",
        }
        self.default_replies = [
            "Hi there!",
            "Hello!",
            "Greetings!",
            "Hey!",
            "Howdy!",
        ]

    @app_commands.command(name="hello", description="Say hello!")
    async def hello(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        if user_id in self.user_replies:
            reply = self.user_replies[user_id]
        else:
            # Pick a reply based on user_id for variety
            reply = self.default_replies[user_id % len(self.default_replies)]
        await interaction.response.send_message(reply)

async def setup(bot):
    await bot.add_cog(ReplyCog(bot))
