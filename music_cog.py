import discord
from discord.ext import commands
from discord import app_commands
from urllib import parse, request
import re
from yt_dlp import YoutubeDL  # use yt-dlp instead of youtube_dl
import json  # <-- Add this import
from discord import ui

class music_cog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        self.is_playing = {}
        self.is_paused = {}
        self.musicQueue = {}
        self.queueIndex = {}

        self.YTDL_OPTIONS = {'format': 'bestaudio', 'nonplaylist': 'True'}
        self.FFMPEG_OPTIONS = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 'options': '-vn'}

        self.embedBlue = 0x2c76dd
        self.embedRed = 0xdf1141
        self.embedGreen = 0x0eaa51

        self.vc = {}

    @commands.Cog.listener()
    async def on_ready(self):
        for guild in self.bot.guilds:
            id = int(guild.id)
            self.musicQueue[id] = []
            self.queueIndex[id] = 0
            self.vc[id] = None
            self.is_paused[id] = self.is_playing[id] = False

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        id = int(member.guild.id)
        if member.id != self.bot.user.id and before.channel != None and after.channel != before.channel:
            remainingChannelMembers = before.channel.members
            if len(remainingChannelMembers) == 1 and remainingChannelMembers[0].id == self.bot.user.id and self.vc[id].is_connected():
                self.is_playing[id] = self.is_paused[id] = False
                self.musicQueue[id] = []
                self.queueIndex[id] = 0
                await self.vc[id].disconnect()

    def now_playing_embed(self, ctx_or_interaction, song):
        # Accepts both ctx (prefix) and interaction (slash)
        author = getattr(ctx_or_interaction, "user", None) or getattr(ctx_or_interaction, "author", None)
        avatar = getattr(author, "avatar_url", None)
        if hasattr(author, "display_avatar"):
            avatar = author.display_avatar.url
        elif hasattr(author, "avatar"):
            avatar = author.avatar.url

        embed = discord.Embed(
            title="Now Playing",
            description=f'[{song["title"]}]({song["link"]})',
            colour=self.embedBlue,
        )
        embed.set_thumbnail(url=song["thumbnail"])
        embed.set_footer(text=f'Song added by: {str(author)}', icon_url=avatar)
        return embed

    def added_song_embed(self, ctx_or_interaction, song):
        author = getattr(ctx_or_interaction, "user", None) or getattr(ctx_or_interaction, "author", None)
        avatar = getattr(author, "avatar_url", None)
        if hasattr(author, "display_avatar"):
            avatar = author.display_avatar.url
        elif hasattr(author, "avatar"):
            avatar = author.avatar.url

        embed = discord.Embed(
            title="Song Added To Queue!",
            description=f'[{song["title"]}]({song["link"]})',
            colour=self.embedRed,
        )
        embed.set_thumbnail(url=song["thumbnail"])
        embed.set_footer(text=f'Song added by: {str(author)}', icon_url=avatar)
        return embed

    def removed_song_embed(self, ctx_or_interaction, song):
        author = getattr(ctx_or_interaction, "user", None) or getattr(ctx_or_interaction, "author", None)
        avatar = getattr(author, "avatar_url", None)
        if hasattr(author, "display_avatar"):
            avatar = author.display_avatar.url
        elif hasattr(author, "avatar"):
            avatar = author.avatar.url

        embed = discord.Embed(
            title="Song Removed From Queue!",
            description=f'[{song["title"]}]({song["link"]})',
            colour=self.embedRed,
        )
        embed.set_thumbnail(url=song["thumbnail"])
        embed.set_footer(
            text=f'Song removed by: {str(author)}', icon_url=avatar)
        return embed

    async def join_VC(self, ctx, channel):
        id = int(ctx.guild.id)
        if self.vc[id] == None or not self.vc[id].is_connected():
            self.vc[id] = await channel.connect()

            if self.vc[id] == None:
                await ctx.send("Could not connect to the vouce channel.")
                return
        else:
            await self.vc[id].move_to(channel)

    def get_YT_title(self, videoID):
        params = {"format": "json",
                  "url": "https://www.youtube.com/watch?v=%s" % videoID}
        url = "https://www.youtube.com/oembed"
        queryString = parse.urlencode(params)
        url = url + "?" + queryString
        with request.urlopen(url) as response:
            responseText = response.read()
            data = json.loads(responseText.decode())
            return data['title']

    def search_YT(self, search):
        queryString = parse.urlencode({'search_query': search})
        htmContent = request.urlopen(
            'http://www.youtube.com/results?' + queryString)
        searchResults = re.findall(
            r'/watch\?v=(.{11})', htmContent.read().decode())  # fixed: use raw string
        # Only keep IDs that are exactly 11 characters (valid YouTube IDs)
        filteredResults = [vid for vid in searchResults if len(vid) == 11]
        return filteredResults[0:10]

    def extract_YT(self, url):
        with YoutubeDL(self.YTDL_OPTIONS) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
            except Exception as e:
                print(f"yt-dlp extraction error: {e}")
                return False
        # Find a direct audio format (not m3u8, not dash)
        audio_url = None
        for f in info.get('formats', []):
            # Print format info for debugging
            print(f"Format: {f.get('format_id')} | acodec: {f.get('acodec')} | vcodec: {f.get('vcodec')} | ext: {f.get('ext')} | url: {f.get('url')}")
            if (
                f.get('acodec') != 'none'
                and f.get('vcodec') == 'none'
                and f.get('protocol', '').startswith('http')
                and not f.get('url', '').endswith('.m3u8')
                and not f.get('url', '').endswith('.mpd')
            ):
                audio_url = f['url']
                print(f"Selected audio url: {audio_url}")
                break
        # fallback to first http audio format if nothing found
        if not audio_url:
            for f in info.get('formats', []):
                if f.get('acodec') != 'none' and f.get('protocol', '').startswith('http'):
                    audio_url = f['url']
                    print(f"Fallback audio url: {audio_url}")
                    break
        # fallback to info['url'] if present
        if not audio_url and 'url' in info:
            audio_url = info['url']
        if not audio_url:
            return False
        return {
            'link': 'https://www.youtube.com/watch?v=' + url,
            'thumbnail': 'https://i.ytimg.com/vi/' + url + '/hqdefault.jpg?sqp=-oaymwEcCOADEI4CSFXyq4qpAw4IARUAAIhCGAFwAcABBg==&rs=AOn4CLD5uL4xKN-IUfez6KIW_j5y70mlig',
            'source': audio_url,
            'title': info['title']
        }

    def play_next(self, ctx):
        id = int(ctx.guild.id)
        if not self.is_playing[id]:
            return
        if self.queueIndex[id] + 1 < len(self.musicQueue[id]):
            self.is_playing[id] = True
            self.queueIndex[id] += 1

            song = self.musicQueue[id][self.queueIndex[id]][0]
            message = self.now_playing_embed(ctx, song)
            # Only send message if ctx is not an Interaction (auto-play)
            if not isinstance(ctx, discord.Interaction):
                coro = ctx.send(embed=message)
                fut = run_coroutine_threadsafe(coro, self.bot.loop)
                try:
                    fut.result()
                except:
                    pass

            self.vc[id].play(discord.FFmpegPCMAudio(
                song['source'], **self.FFMPEG_OPTIONS), after=lambda e: self.play_next(ctx))
        else:
            self.queueIndex[id] += 1
            self.is_playing[id] = False

    async def play_music(self, ctx):
        id = int(ctx.guild.id)
        if self.queueIndex[id] < len(self.musicQueue[id]):
            self.is_playing[id] = True
            self.is_paused[id] = False

            await self.join_VC(ctx, self.musicQueue[id][self.queueIndex[id]][1])

            song = self.musicQueue[id][self.queueIndex[id]][0]
            message = self.now_playing_embed(ctx, song)
            # Only send message if ctx is not an Interaction (auto-play)
            if not isinstance(ctx, discord.Interaction):
                await ctx.send(embed=message)

            self.vc[id].play(discord.FFmpegPCMAudio(
                song['source'], **self.FFMPEG_OPTIONS), after=lambda e: self.play_next(ctx))
        else:
            if not isinstance(ctx, discord.Interaction):
                await ctx.send("There are no songs in the queue to be played.")
            self.queueIndex[id] += 1
            self.is_playing[id] = False

    @app_commands.command(
        name="play",
        description="Plays (or resumes) the audio of a specified YouTube video"
    )
    async def play(self, interaction: discord.Interaction, search: str = None):
        id = int(interaction.guild.id)
        try:
            userChannel = interaction.user.voice.channel
        except:
            await interaction.response.send_message("You must be connected to a voice channel.", ephemeral=True)
            return

        if id not in self.musicQueue:
            self.musicQueue[id] = []
            self.queueIndex[id] = 0
            self.vc[id] = None
            self.is_paused[id] = False
            self.is_playing[id] = False

        # Remove defer, handle response immediately
        if not search:
            if len(self.musicQueue[id]) == 0:
                await interaction.response.send_message("There are no songs to be played in the queue.")
                return
            elif not self.is_playing[id]:
                if self.musicQueue[id] == None or self.vc[id] == None:
                    await self.play_music(interaction)
                else:
                    self.is_paused[id] = False
                    self.is_playing[id] = True
                    self.vc[id].resume()
            else:
                return
        else:
            yt_url = 'https://www.youtube.com/watch?v=' + self.search_YT(search)[0]
            song = self.extract_YT(yt_url)
            if type(song) == type(True):
                await interaction.response.send_message("Could not download the song. Incorrect format, try some different keywords.")
            else:
                self.musicQueue[id].append([song, userChannel])
                if not self.is_playing[id]:
                    message = self.now_playing_embed(interaction, song)
                    await interaction.response.send_message(embed=message)
                    await self.play_music(interaction)
                else:
                    message = self.added_song_embed(interaction, song)
                    await interaction.response.send_message(embed=message)

    @app_commands.command(
        name="add",
        description="Adds the first search result to the queue"
    )
    async def add(self, interaction: discord.Interaction, search: str):
        try:
            userChannel = interaction.user.voice.channel
        except:
            await interaction.response.send_message("You must be in a voice channel.", ephemeral=True)
            return
        id = int(interaction.guild.id)
        if id not in self.musicQueue:
            self.musicQueue[id] = []
        yt_url = 'https://www.youtube.com/watch?v=' + self.search_YT(search)[0]
        song = self.extract_YT(yt_url)
        if type(song) == type(False):
            await interaction.response.send_message("Could not download the song. Incorrect format, try different keywords.")
            return
        else:
            self.musicQueue[id].append([song, userChannel])
            message = self.added_song_embed(interaction, song)
            await interaction.response.send_message(embed=message)

    @app_commands.command(
        name="remove",
        description="Removes the last song in the queue"
    )
    async def remove(self, interaction: discord.Interaction):
        id = int(interaction.guild.id)
        if self.musicQueue.get(id, []) != []:
            song = self.musicQueue[id][-1][0]
            removeSongEmbed = self.removed_song_embed(interaction, song)
            await interaction.response.send_message(embed=removeSongEmbed)
        else:
            await interaction.response.send_message("There are no songs to be removed in the queue.")
        self.musicQueue[id] = self.musicQueue[id][:-1]
        if self.musicQueue[id] == []:
            if self.vc[id] != None and self.is_playing[id]:
                self.is_playing[id] = self.is_paused[id] = False
                await self.vc[id].disconnect()
                self.vc[id] = None
            self.queueIndex[id] = 0
        elif self.queueIndex[id] == len(self.musicQueue[id]) and self.vc[id] != None and self.vc[id]:
            self.vc[id].pause()
            self.queueIndex[id] -= 1
            await self.play_music(interaction)

    @app_commands.command(
        name="search",
        description="Provides a list of YouTube search results"
    )
    async def search(self, interaction: discord.Interaction, search: str):
        try:
            userChannel = interaction.user.voice.channel
        except:
            await interaction.response.send_message("You must be connected to a voice channel.", ephemeral=True)
            return

        await interaction.response.send_message("Fetching search results . . .")

        songTokens = self.search_YT(search)
        songNames = []
        options = []
        used_tokens = set()
        for i, token in enumerate(songTokens):
            url = 'https://www.youtube.com/watch?v=' + token
            name = self.get_YT_title(token)
            songNames.append(name)
            # Ensure each option value is unique by appending the index if needed
            unique_token = token
            if unique_token in used_tokens:
                unique_token = f"{token}_{i}"
            used_tokens.add(unique_token)
            options.append(discord.SelectOption(label=f"{i+1}. {name[:90]}", value=unique_token, description=name[:100]))

        class SongSelect(ui.View):
            def __init__(self, parent, tokens, names, user_channel):
                super().__init__(timeout=60)
                self.tokens = tokens
                self.names = names
                self.user_channel = user_channel
                self.parent = parent

                self.add_item(self.SongDropdown(tokens, names))

            class SongDropdown(ui.Select):
                def __init__(self, tokens, names):
                    # Ensure unique values for each option
                    used = set()
                    options = []
                    for i in range(len(tokens)):
                        val = tokens[i]
                        if val in used:
                            val = f"{val}_{i}"
                        used.add(val)
                        options.append(
                            discord.SelectOption(
                                label=f"{i+1}. {names[i][:90]}",
                                value=val,
                                description=names[i][:100]
                            )
                        )
                    super().__init__(placeholder="Select a song to add to the queue", min_values=1, max_values=1, options=options)

                async def callback(self, interaction2: discord.Interaction):
                    # Remove any appended index to get the original token
                    token = self.values[0].split('_')[0]
                    yt_url = 'https://www.youtube.com/watch?v=' + token
                    song = self.view.parent.extract_YT(yt_url)
                    if type(song) == type(False):
                        await interaction2.response.edit_message(content="Could not download the song. Incorrect format, try different keywords.", embed=None, view=None)
                        return
                    id = int(interaction2.guild.id)
                    # Ensure the queue exists for this guild
                    if id not in self.view.parent.musicQueue:
                        self.view.parent.musicQueue[id] = []
                        self.view.parent.queueIndex[id] = 0
                        self.view.parent.vc[id] = None
                        self.view.parent.is_paused[id] = False
                        self.view.parent.is_playing[id] = False
                    self.view.parent.musicQueue[id].append([song, self.view.user_channel])
                    embed = discord.Embed(
                        title="Song Added To Queue!",
                        description=f'[{song["title"]}]({song["link"]})',
                        colour=self.view.parent.embedRed,
                    )
                    embed.set_thumbnail(url=song["thumbnail"])
                    embed.set_footer(text=f'Song added by: {interaction2.user}', icon_url=interaction2.user.display_avatar.url)
                    await interaction2.response.edit_message(content="Song added to queue!", embed=embed, view=None)

        embedText = ""
        for i, name in enumerate(songNames):
            url = 'https://www.youtube.com/watch?v=' + songTokens[i]
            embedText += f"{i+1} - [{name}]({url})\n"

        searchResults = discord.Embed(
            title="Search Results",
            description=embedText,
            colour=self.embedRed
        )
        await interaction.followup.send(embed=searchResults, view=SongSelect(self, songTokens, songNames, userChannel))

    @ commands.command(
        name="pause",
        aliases=["stop", "pa"],
        help="Pauses the current song being played"
    )
    async def pause(self, ctx):
        id = int(ctx.guild.id)
        if not self.vc[id]:
            await ctx.send("There is no audio to be paused at the moment.")
        elif self.is_playing[id]:
            await ctx.send("Audio paused!")
            self.is_playing[id] = False
            self.is_paused[id] = True
            self.vc[id].pause()

    @ commands.command(
        name="resume",
        aliases=["re"],
        help="Resumes a paused song"
    )
    async def resume(self, ctx):
        id = int(ctx.guild.id)
        if not self.vc[id]:
            await ctx.send("There is no audio to be played at the moment.")
        elif self.is_paused[id]:
            await ctx.send("The audio is now playing!")
            self.is_playing[id] = True
            self.is_paused[id] = False
            self.vc[id].resume()

    @ commands.command(
        name="previous",
        aliases=["pre", "pr"],
        help="Plays the previous song in the queue"
    )
    async def previous(self, ctx):
        id = int(ctx.guild.id)
        if self.vc[id] == None:
            await ctx.send("You need to be in a VC to use this command.")
        elif self.queueIndex[id] <= 0:
            await ctx.send("There is no previous song in the queue. Replaying current song.")
            self.vc[id].pause()
            await self.play_music(ctx)
        elif self.vc[id] != None and self.vc[id]:
            self.vc[id].pause()
            self.queueIndex[id] -= 1
            await self.play_music(ctx)

    @app_commands.command(
        name="skip",
        description="Skips to the next song in the queue."
    )
    async def skip(self, interaction: discord.Interaction):
        id = int(interaction.guild.id)
        if self.vc[id] is None:
            await interaction.response.send_message("You need to be in a VC to use this command.")
        elif self.queueIndex[id] >= len(self.musicQueue[id]) - 1:
            await interaction.response.send_message("There is no next song in the queue. Replaying current song.")
            self.vc[id].pause()
            await self.play_music(interaction)
        elif self.vc[id]:
            self.vc[id].pause()
            self.queueIndex[id] += 1
            await self.play_music(interaction)

    @app_commands.command(
        name="previous",
        description="Plays the previous song in the queue."
    )
    async def previous(self, interaction: discord.Interaction):
        id = int(interaction.guild.id)
        if self.vc[id] is None:
            await interaction.response.send_message("You need to be in a VC to use this command.")
        elif self.queueIndex[id] <= 0:
            await interaction.response.send_message("There is no previous song in the queue. Replaying current song.")
            self.vc[id].pause()
            await self.play_music(interaction)
        elif self.vc[id]:
            self.vc[id].pause()
            self.queueIndex[id] -= 1
            await self.play_music(interaction)

    @ commands.command(
        name="queue",
        aliases=["list", "q"],
        help="Lists the next few songs in the queue."
    )
    async def queue(self, ctx):
        id = int(ctx.guild.id)
        returnValue = ""
        if self.musicQueue[id] == []:
            await ctx.send("There are no songs in the queue.")
            return

        for i in range(self.queueIndex[id], len(self.musicQueue[id])):
            upNextSongs = len(self.musicQueue[id]) - self.queueIndex[id]
            if i > 5 + upNextSongs:
                break
            returnIndex = i - self.queueIndex[id]
            if returnIndex == 0:
                returnIndex = "Playing"
            elif returnIndex == 1:
                returnIndex = "Next"
            returnValue += f"{returnIndex} - [{self.musicQueue[id][i][0]['title']}]({self.musicQueue[id][i][0]['link']})\n"

            if returnValue == "":
                await ctx.send("There are no songs in the queue.")
                return

        queue = discord.Embed(
            title="Current Queue",
            description=returnValue,
            colour=self.embedGreen
        )
        await ctx.send(embed=queue)

    @app_commands.command(
        name="queue",
        description="Lists the next few songs in the queue."
    )
    async def queue(self, interaction: discord.Interaction):
        id = int(interaction.guild.id)
        if id not in self.musicQueue or not self.musicQueue[id]:
            await interaction.response.send_message("There are no songs in the queue.")
            return

        returnValue = ""
        for i in range(self.queueIndex[id], len(self.musicQueue[id])):
            upNextSongs = len(self.musicQueue[id]) - self.queueIndex[id]
            if i > 5 + upNextSongs:
                break
            returnIndex = i - self.queueIndex[id]
            if returnIndex == 0:
                returnIndex = "Playing"
            elif returnIndex == 1:
                returnIndex = "Next"
            returnValue += f"{returnIndex} - [{self.musicQueue[id][i][0]['title']}]({self.musicQueue[id][i][0]['link']})\n"

        if returnValue == "":
            await interaction.response.send_message("There are no songs in the queue.")
            return

        queue_embed = discord.Embed(
            title="Current Queue",
            description=returnValue,
            colour=self.embedGreen
        )
        await interaction.response.send_message(embed=queue_embed)

    @app_commands.command(
        name="clear",
        description="Clears all of the songs from the queue."
    )
    async def clear(self, interaction: discord.Interaction):
        id = int(interaction.guild.id)
        if id in self.vc and self.vc[id] is not None and self.is_playing.get(id, False):
            self.is_playing[id] = self.is_paused[id] = False
            self.vc[id].stop()
        if id in self.musicQueue and self.musicQueue[id]:
            self.musicQueue[id] = []
            await interaction.response.send_message("The music queue has been cleared.")
        else:
            await interaction.response.send_message("The queue is already empty.")
        self.queueIndex[id] = 0

    @app_commands.command(
        name="join",
        description="Connects PotatoJr. to the voice channel."
    )
    async def join(self, interaction: discord.Interaction):
        if interaction.user.voice:
            userChannel = interaction.user.voice.channel
            await self.join_VC(interaction, userChannel)
            await interaction.response.send_message(f'PotatoJr. has joined {userChannel}')
        else:
            await interaction.response.send_message("You need to be connected to a voice channel.")

    @app_commands.command(
        name="leave",
        description="Removes PotatoJr. from the voice channel and clears the queue."
    )
    async def leave(self, interaction: discord.Interaction):
        id = int(interaction.guild.id)
        self.is_playing[id] = self.is_paused[id] = False
        self.musicQueue[id] = []
        self.queueIndex[id] = 0
        if self.vc.get(id):
            await interaction.response.send_message("PotatoJr. has left the chat")
            await self.vc[id].disconnect()
            self.vc[id] = None
        else:
           
            await interaction.response.send_message("I'm not connected to a voice channel.", ephemeral=True)

    @ commands.command(
        name="joinvc",
        aliases=["j"],
        help="Connects PotatoJr. to the voice channel"
    )
    async def joinvc(self, ctx):
        if ctx.author.voice:
            userChannel = ctx.author.voice.channel
            await self.join_VC(ctx, userChannel)
            await ctx.send(f'PotatoJr. has joined {userChannel}')
        else:
            await ctx.send("You need to be connected to a voice channel.")

    @ commands.command(
        name="leavevc",
        aliases=["l"],
        help="Removes PotatoJr. from the voice channel and clears the queue"
    )
    async def leavevc(self, ctx):
        id = int(ctx.guild.id)
        self.is_playing[id] = self.is_paused[id] = False
        self.musicQueue[id] = []
        self.queueIndex[id] = 0
        if self.vc[id] != None:
            await ctx.send("PotatoJr. has left the chat")
            await self.vc[id].disconnect()
            self.vc[id] = None
        else:
            await ctx.send("I'm not connected to a voice channel.")

    @app_commands.command(
        name="pause",
        description="Pauses the current song being played"
    )
    async def pause_slash(self, interaction: discord.Interaction):
        id = int(interaction.guild.id)
        if not self.vc.get(id):
            await interaction.response.send_message("There is no audio to be paused at the moment.", ephemeral=True)
        elif self.is_playing.get(id, False):
            await interaction.response.send_message("Audio paused!", ephemeral=True)
            self.is_playing[id] = False
            self.is_paused[id] = True
            self.vc[id].pause()

    @app_commands.command(
        name="resume",
        description="Resumes a paused song"
    )
    async def resume_slash(self, interaction: discord.Interaction):
        id = int(interaction.guild.id)
        if not self.vc.get(id):
            await interaction.response.send_message("There is no audio to be played at the moment.", ephemeral=True)
        elif self.is_paused.get(id, False):
            await interaction.response.send_message("The audio is now playing!", ephemeral=True)
            self.is_playing[id] = True
            self.is_paused[id] = False
            self.vc[id].resume()

async def setup(bot):
    await bot.add_cog(music_cog(bot))



