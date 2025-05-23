import discord
from discord.ext import commands
from discord import app_commands
from urllib import parse, request
import re
from yt_dlp import YoutubeDL  # use yt-dlp instead of youtube_dl
import json  # <-- Add this import
from discord import ui
from asyncio import run_coroutine_threadsafe  # <-- Add this import

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
        avatar = None
        if author is not None:
            if hasattr(author, "display_avatar"):
                avatar = author.display_avatar.url
            elif hasattr(author, "avatar") and author.avatar:
                avatar = author.avatar.url
            elif hasattr(author, "avatar_url"):
                avatar = author.avatar_url
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
        avatar = None
        if author is not None:
            if hasattr(author, "display_avatar"):
                avatar = author.display_avatar.url
            elif hasattr(author, "avatar") and author.avatar:
                avatar = author.avatar.url
            elif hasattr(author, "avatar_url"):
                avatar = author.avatar_url
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
        avatar = None
        if author is not None:
            if hasattr(author, "display_avatar"):
                avatar = author.display_avatar.url
            elif hasattr(author, "avatar") and author.avatar:
                avatar = author.avatar.url
            elif hasattr(author, "avatar_url"):
                avatar = author.avatar_url
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
        if not info:
            return False
        # If it's a playlist, return a list of song dicts
        if isinstance(info, dict) and 'entries' in info and info['entries']:
            songs = []
            for entry in info['entries']:
                if not entry:
                    continue
                # Find a direct audio format (not m3u8, not dash)
                audio_url = None
                for f in entry.get('formats', []) if entry else []:
                    if (
                        f.get('acodec') != 'none'
                        and f.get('vcodec') == 'none'
                        and f.get('protocol', '').startswith('http')
                        and not f.get('url', '').endswith('.m3u8')
                        and not f.get('url', '').endswith('.mpd')
                    ):
                        audio_url = f['url']
                        break
                if not audio_url:
                    for f in entry.get('formats', []) if entry else []:
                        if f.get('acodec') != 'none' and f.get('protocol', '').startswith('http'):
                            audio_url = f['url']
                            break
                if not audio_url and isinstance(entry, dict) and 'url' in entry:
                    audio_url = entry['url']
                if not audio_url:
                    continue
                songs.append({
                    'link': 'https://www.youtube.com/watch?v=' + entry['id'],
                    'thumbnail': 'https://i.ytimg.com/vi/' + entry['id'] + '/hqdefault.jpg',
                    'source': audio_url,
                    'title': entry['title']
                })
            return songs
        # fallback to single video extraction
        audio_url = None
        for f in info.get('formats', []) if info else []:
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
        if not audio_url:
            for f in info.get('formats', []) if info else []:
                if f.get('acodec') != 'none' and f.get('protocol', '').startswith('http'):
                    audio_url = f['url']
                    print(f"Fallback audio url: {audio_url}")
                    break
        if not audio_url and isinstance(info, dict) and 'url' in info:
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
        if not self.is_playing.get(id, False):
            return
        if self.queueIndex.get(id, 0) + 1 < len(self.musicQueue.get(id, [])):
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

            vc = self.vc.get(id)
            if vc:
                # Only pass valid keyword arguments to FFmpegPCMAudio
                thumbnail = song.get("thumbnail") or ""
                vc.play(discord.FFmpegPCMAudio(
                    song['source'],
                    before_options=self.FFMPEG_OPTIONS['before_options'],
                    options=self.FFMPEG_OPTIONS['options']
                ), after=lambda e: self.play_next(ctx))
        else:
            self.queueIndex[id] += 1
            self.is_playing[id] = False

    async def play_music(self, ctx):
        id = int(ctx.guild.id)
        if self.queueIndex.get(id, 0) < len(self.musicQueue.get(id, [])):
            self.is_playing[id] = True
            self.is_paused[id] = False

            await self.join_VC(ctx, self.musicQueue[id][self.queueIndex[id]][1])

            song = self.musicQueue[id][self.queueIndex[id]][0]
            message = self.now_playing_embed(ctx, song)
            # Only send message if ctx is not an Interaction (auto-play)
            if not isinstance(ctx, discord.Interaction):
                await ctx.send(embed=message)

            vc = self.vc.get(id)
            if vc:
                vc.play(discord.FFmpegPCMAudio(
                    song['source'],
                    before_options=self.FFMPEG_OPTIONS['before_options'],
                    options=self.FFMPEG_OPTIONS['options']
                ), after=lambda e: self.play_next(ctx))
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
        id = int(getattr(interaction.guild, "id", 0) or 0)
        try:
            user_voice = getattr(interaction.user, "voice", None)
            userChannel = user_voice.channel if user_voice and user_voice.channel else None
            if userChannel is None:
                raise Exception()
        except:
            await interaction.response.send_message("You must be connected to a voice channel.", ephemeral=False)
            return

        if id not in self.musicQueue:
            self.musicQueue[id] = []
            self.queueIndex[id] = 0
            self.vc[id] = None
            self.is_paused[id] = False
            self.is_playing[id] = False

        if not search:
            # Always respond immediately to avoid Discord timeout
            if len(self.musicQueue[id]) == 0:
                await interaction.response.send_message("There are no songs to be played in the queue.")
                return
            elif not self.is_playing.get(id, False):
                await interaction.response.send_message("Resuming playback or starting the queue...")
                if self.musicQueue[id] == None or self.vc[id] == None:
                    await self.play_music(interaction)
                else:
                    self.is_paused[id] = False
                    self.is_playing[id] = True
                    self.vc[id].resume()
            else:
                await interaction.response.send_message("Music is already playing.")
            return
        else:
            # Respond immediately to avoid Discord timeout
            await interaction.response.send_message("Processing your request, please wait...")

            # Improved: handle empty search results and allow direct playlist links
            if "youtube.com/watch" not in search and "youtu.be/" not in search and "playlist" not in search:
                search_results = self.search_YT(search)
                if not search_results:
                    await interaction.followup.send("No results found for your search.")
                    return
                yt_url = 'https://www.youtube.com/watch?v=' + search_results[0]
            else:
                yt_url = search
            # Download/extract after initial response
            songs = self.extract_YT(yt_url)
            if songs is False:
                await interaction.followup.send("Could not download the song. Incorrect format, try some different keywords.")
            elif isinstance(songs, list):
                for song in songs:
                    self.musicQueue[id].append([song, userChannel])
                await interaction.followup.send(f"Added {len(songs)} songs from the playlist to the queue.")
                # Always start playing after adding playlist if not already playing
                if not self.is_playing.get(id, False) or self.vc[id] is None or not self.vc[id].is_connected():
                    self.queueIndex[id] = 0
                    await self.play_music(interaction)
            else:
                self.musicQueue[id].append([songs, userChannel])
                if not self.is_playing[id]:
                    message = self.now_playing_embed(interaction, songs)
                    await interaction.followup.send(embed=message)
                    await self.play_music(interaction)
                else:
                    message = self.added_song_embed(interaction, songs)
                    await interaction.followup.send(embed=message)

    @app_commands.command(
        name="add",
        description="Adds the first search result to the queue"
    )
    async def add(self, interaction: discord.Interaction, search: str):
        id = int(getattr(interaction.guild, "id", 0) or 0)
        try:
            user_voice = getattr(interaction.user, "voice", None)
            userChannel = user_voice.channel if user_voice and user_voice.channel else None
            if userChannel is None:
                raise Exception()
        except:
            await interaction.response.send_message("You must be in a voice channel.", ephemeral=False)
            return
        if id not in self.musicQueue:
            self.musicQueue[id] = []
        # Respond immediately to avoid Discord timeout
        await interaction.response.send_message("Processing your request, please wait...")
        # Improved: handle empty search results and allow direct playlist links
        if "youtube.com/watch" not in search and "youtu.be/" not in search and "playlist" not in search:
            search_results = self.search_YT(search)
            if not search_results:
                await interaction.followup.send("No results found for your search.")
                return
            yt_url = 'https://www.youtube.com/watch?v=' + search_results[0]
        else:
            yt_url = search
        songs = self.extract_YT(yt_url)
        if songs is False:
            await interaction.followup.send("Could not download the song. Incorrect format, try different keywords.")
            return
        elif isinstance(songs, list):
            for song in songs:
                self.musicQueue[id].append([song, userChannel])
            await interaction.followup.send(f"Added {len(songs)} songs from the playlist to the queue.")
        else:
            self.musicQueue[id].append([songs, userChannel])
            message = self.added_song_embed(interaction, songs)
            await interaction.followup.send(embed=message)

    @app_commands.command(
        name="remove",
        description="Removes the last song in the queue"
    )
    async def remove(self, interaction: discord.Interaction):
        id = int(getattr(interaction.guild, "id", 0) or 0)
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
        id = int(getattr(interaction.guild, "id", 0) or 0)
        try:
            userChannel = getattr(interaction.user, "voice", None)
            if userChannel is None or userChannel.channel is None:
                raise Exception()
            userChannel = userChannel.channel
        except:
            await interaction.response.send_message("You must be connected to a voice channel.", ephemeral=False)
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

                self.add_item(self.SongDropdown(tokens, names, parent, user_channel))

            class SongDropdown(ui.Select):
                def __init__(self, tokens, names, parent, user_channel):
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
                    self.parent = parent
                    self.user_channel = user_channel

                async def callback(self, interaction):
                    # Remove any appended index to get the original token
                    token = self.values[0].split('_')[0]
                    yt_url = 'https://www.youtube.com/watch?v=' + token
                    song = self.parent.extract_YT(yt_url)
                    if type(song) == type(False):
                        await interaction.response.edit_message(content="Could not download the song. Incorrect format, try different keywords.", embed=None, view=None)
                        return
                    id = int(interaction.guild.id)
                    # Ensure the queue exists for this guild
                    if id not in self.parent.musicQueue:
                        self.parent.musicQueue[id] = []
                        self.parent.queueIndex[id] = 0
                        self.parent.vc[id] = None
                        self.parent.is_paused[id] = False
                        self.parent.is_playing[id] = False
                    self.parent.musicQueue[id].append([song, self.user_channel])
                    embed = discord.Embed(
                        title="Song Added To Queue!",
                        description=f'[{song["title"]}]({song["link"]})',
                        colour=self.parent.embedRed,
                    )
                    user = getattr(interaction, "user", None)
                    avatar = None
                    if user is not None:
                        if hasattr(user, "display_avatar"):
                            avatar = user.display_avatar.url
                        elif hasattr(user, "avatar") and user.avatar:
                            avatar = user.avatar.url
                        elif hasattr(user, "avatar_url"):
                            avatar = user.avatar_url
                    embed.set_thumbnail(url=song.get("thumbnail") or "")
                    embed.set_footer(text=f'Song added by: {user}', icon_url=avatar)
                    await interaction.response.edit_message(content="Song added to queue!", embed=embed, view=None)

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

    @app_commands.command(
        name="skip",
        description="Skips to the next song in the queue."
    )
    async def skip(self, interaction: discord.Interaction):
        id = int(getattr(interaction.guild, "id", 0) or 0)
        if self.vc.get(id) is None:
            await interaction.response.send_message("You need to be in a VC to use this command.")
        elif self.queueIndex.get(id, 0) >= len(self.musicQueue.get(id, [])) - 1:
            await interaction.response.send_message("There is no next song in the queue. Replaying current song.")
            self.vc[id].pause()
            await self.play_music(interaction)
        elif self.vc[id]:
            self.vc[id].pause()
            self.queueIndex[id] += 1
            await self.play_music(interaction)
            await interaction.response.send_message("Skipped to the next song in the queue.")

    @app_commands.command(
        name="previous",
        description="Plays the previous song in the queue."
    )
    async def previous_slash(self, interaction: discord.Interaction):
        id = int(getattr(interaction.guild, "id", 0) or 0)
        if self.vc.get(id) is None:
            await interaction.response.send_message("You need to be in a VC to use this command.")
        elif self.queueIndex.get(id, 0) <= 0:
            await interaction.response.send_message("There is no previous song in the queue. Replaying current song.")
            self.vc[id].pause()
            await self.play_music(interaction)
        elif self.vc[id]:
            self.vc[id].pause()
            self.queueIndex[id] -= 1
            await self.play_music(interaction)

    @commands.command(
        name="queue",
        aliases=["list", "q"],
        help="Lists the next few songs in the queue."
    )
    async def queue(self, ctx):
        id = int(ctx.guild.id)
        returnValue = ""
        if self.musicQueue.get(id, []) == []:
            await ctx.send("There are no songs in the queue.")
            return

        for i in range(self.queueIndex.get(id, 0), len(self.musicQueue.get(id, []))):
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
    async def queue_slash(self, interaction: discord.Interaction):
        id = int(getattr(interaction.guild, "id", 0) or 0)
        if id not in self.musicQueue or not self.musicQueue[id]:
            await interaction.response.send_message("There are no songs in the queue.")
            return

        returnValue = ""
        for i in range(self.queueIndex.get(id, 0), len(self.musicQueue.get(id, []))):
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
        id = int(getattr(interaction.guild, "id", 0) or 0)
        # Only clear songs that are not currently playing
        if id in self.musicQueue and self.musicQueue[id]:
            # Keep the currently playing song (at queueIndex[id]), remove the rest
            if self.is_playing.get(id, False) and self.queueIndex.get(id, 0) < len(self.musicQueue[id]):
                self.musicQueue[id] = [self.musicQueue[id][self.queueIndex[id]]]
                self.queueIndex[id] = 0
                await interaction.response.send_message("The queue has been cleared, but the current song will keep playing.")
            else:
                self.musicQueue[id] = []
                self.queueIndex[id] = 0
                await interaction.response.send_message("The music queue has been cleared.")
        else:
            await interaction.response.send_message("The queue is already empty.")
        self.queueIndex[id] = 0

    @app_commands.command(
        name="join",
        description="Connects PotatoJr. to the voice channel."
    )
    async def join(self, interaction: discord.Interaction):
        user_voice = getattr(interaction.user, "voice", None)
        userChannel = user_voice.channel if user_voice and user_voice.channel else None
        if userChannel:
            await self.join_VC(interaction, userChannel)
            await interaction.response.send_message(f'PotatoJr. has joined {userChannel}')
        else:
            await interaction.response.send_message("You need to be connected to a voice channel.")

    @app_commands.command(
        name="leave",
        description="Removes PotatoJr. from the voice channel and clears the queue."
    )
    async def leave(self, interaction: discord.Interaction):
        id = int(getattr(interaction.guild, "id", 0) or 0)
        self.is_playing[id] = self.is_paused[id] = False
        self.musicQueue[id] = []
        self.queueIndex[id] = 0
        if self.vc.get(id):
            await interaction.response.send_message("PotatoJr. has left the chat")
            await self.vc[id].disconnect()
            self.vc[id] = None
        else:
            await interaction.response.send_message("I'm not connected to a voice channel.", ephemeral=False)

    @commands.command(
        name="joinvc",
        aliases=["j"],
        help="Connects PotatoJr. to the voice channel"
    )
    async def joinvc(self, ctx):
        user_voice = getattr(ctx.author, "voice", None)
        userChannel = user_voice.channel if user_voice and user_voice.channel else None
        if userChannel:
            await self.join_VC(ctx, userChannel)
            await ctx.send(f'PotatoJr. has joined {userChannel}')
        else:
            await ctx.send("You need to be connected to a voice channel.")

    @commands.command(
        name="leavevc",
        aliases=["l"],
        help="Removes PotatoJr. from the voice channel and clears the queue"
    )
    async def leavevc(self, ctx):
        id = int(getattr(ctx.guild, "id", 0) or 0)
        self.is_playing[id] = self.is_paused[id] = False
        self.musicQueue[id] = []
        self.queueIndex[id] = 0
        if self.vc.get(id) is not None:
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
        id = int(getattr(interaction.guild, "id", 0) or 0)
        if not self.vc.get(id):
            await interaction.response.send_message("There is no audio to be paused at the moment.", ephemeral=False)
        elif self.is_playing.get(id, False):
            await interaction.response.send_message("Audio paused!", ephemeral=False)
            self.is_playing[id] = False
            self.is_paused[id] = True
            self.vc[id].pause()

    @app_commands.command(
        name="resume",
        description="Resumes a paused song"
    )
    async def resume_slash(self, interaction: discord.Interaction):
        id = int(getattr(interaction.guild, "id", 0) or 0)
        if not self.vc.get(id):
            await interaction.response.send_message("There is no audio to be played at the moment.", ephemeral=False)
        elif self.is_paused.get(id, False):
            await interaction.response.send_message("The audio is now playing!", ephemeral=False)
            self.is_playing[id] = True
            self.is_paused[id] = False
            self.vc[id].resume()

    @app_commands.command(
        name="stop",
        description="Stops the current song, clears the queue, and leaves the voice channel."
    )
    async def stop(self, interaction: discord.Interaction):
        id = int(getattr(interaction.guild, "id", 0) or 0)
        # Stop playback
        if self.vc.get(id) and self.vc[id].is_connected():
            self.vc[id].stop()
            await self.vc[id].disconnect()
            self.vc[id] = None
        # Clear queue and reset state
        self.musicQueue[id] = []
        self.queueIndex[id] = 0
        self.is_playing[id] = False
        self.is_paused[id] = False
        await interaction.response.send_message("Stopped playback, cleared the queue, and left the voice channel.")

async def setup(bot):
    await bot.add_cog(music_cog(bot))



