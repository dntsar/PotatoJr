import discord
from discord.ext import commands
from discord import app_commands
import asyncio
from asyncio import run_coroutine_threadsafe
from urllib import parse, request
import re
import json
import os
from youtube_dl import YoutubeDL

class Client(commands.Bot):
    async def setup_hook(self):
        # Use setup_hook for loading cogs/extensions and syncing commands
        await self.load_extension("music_cog")
        try:
            # Remove guild argument to sync globally
            synced = await self.tree.sync()
            print(f'Synced {len(synced)} global commands')
        except Exception as e:
            print(f'Error: {e}')

    async def on_ready(self):
        print(f'Logged on as {self.user}!')

    async def on_message(self, message):
        print(f'Message from {message.author}: {message.content}')

intents = discord.Intents.default()
intents.message_content = True
bot = Client(command_prefix='!', intents=intents)


# Remove guild=GUILD_ID from the decorator to make the command global
@bot.tree.command(name="hello", description="Say hello!")
async def sayHello(interaction: discord.Interaction):
    await interaction.response.send_message("Hi there!")

with open('token.txt', 'r') as file:
    token = file.readlines()[0]

bot.run(token)