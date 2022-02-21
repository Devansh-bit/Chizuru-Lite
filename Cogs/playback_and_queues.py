from typing import List, Tuple
import aiohttp
from discord.ext import commands
from discord import slash_command, Option, Embed
from utils.utils import error_embed, info_embed
from utils.errors import *
import discord
import math
import random
import spotipy
from base_classes_rewrite.music import *
from base_classes_rewrite.spotify import *
from base_classes_rewrite.models import *
import re
from urllib import parse
import urllib.parse

server_array = None
def setup(bot):
    global server_array
    server_array = bot.config.debug_guilds
    bot.add_cog(PlaybackAndQueues(bot))

def parse_duration(duration: int):
    minutes, seconds = divmod(duration, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)

    duration = []
    if days > 0:
        duration.append('{} days'.format(days))
    if hours > 0:
        duration.append('{} hours'.format(hours))
    if minutes > 0:
        duration.append('{} minutes'.format(minutes))
    if seconds > 0:
        duration.append('{} seconds'.format(seconds))

    return ', '.join(duration)

class DropdownView(discord.ui.View):
    def __init__(self, matches, playlist, state):
        super().__init__()
        self.add_item(RemoveDropdown(matches, playlist, state))
        self.add_item(CancelButton())


class CancelButton(discord.ui.Button):
    def __init__(self):
        super().__init__(style=discord.ButtonStyle.red,
                         label="Cancel")

    async def callback(self, interaction: discord.Interaction):
        self.view.stop()
        await interaction.message.edit(embed=info_embed(interaction, description="**Cancelled command**"), view=None)


class RemoveDropdown(discord.ui.Select):
    def __init__(self, matches: List[Tuple[str, int, YoutubeSong]], playlist: bool, state):
        options = []
        names = []
        to_remove = []
        if playlist:
            for i in range(len(matches)):
                match = matches[i]
                if match[2].title in names:
                    to_remove.append(i)
                names.append(match[2].title)
                options.append(discord.SelectOption(label=match[2].title))
        else:
            for i in range(len(matches)):
                match = matches[i]
                if match[2].title in names:
                    to_remove.append(i)
                names.append(match[2].title)
                options.append(discord.SelectOption(
                    label=match[2].track_description, value=match[2].title))
        for index in sorted(to_remove, reverse=True):
            del names[index]
            del options[index]
            del matches[index]

        self.names = names
        self.matches = matches
        self.playlist = playlist
        self.state = state
        super().__init__(
            placeholder=f"Select {'playlist' if playlist else 'song'} to remove",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        self.view.stop()
        label = self.values[0]
        item_to_remove = self.matches[self.names.index(label)][2]
        if self.playlist:
            for song in item_to_remove.tracks:
                try:
                    self.state.queue._queue.remove(song)
                except Exception:
                    logger.exception("Error removing song from queue")
            self.state.queue.playlists.remove(item_to_remove)
        else:
            self.state.queue._queue.remove(item_to_remove)
            if item_to_remove.playlist:
                item_to_remove.playlist.tracks.remove(item_to_remove)
        await interaction.message.edit(embed=info_embed(interaction, description=f"**Removed {item_to_remove.queue_field} from the queue**"), view=None)
        del item_to_remove




class PlaybackAndQueues(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.voice_state_manager = VoiceStateManager(bot)
        global vcm
        self.sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials())
        vcm = self.voice_state_manager
        self.session = aiohttp.ClientSession()

    @slash_command(guild_ids=server_array)
    async def lyrics(self, ctx: discord.ApplicationContext, title: str = None):
        await ctx.defer()
        state = self.voice_state_manager.get_raw_voice_state(ctx)
        if title:
            response_json = await fetch(self.session, f"https://some-random-api.ml/lyrics?title={urllib.parse.quote_plus(title)}")
        elif state and state.voice_client.is_playing() and state.song:
            title = state.song.title if hasattr(
                state.song, "title") else state.song.name
            response_json = await fetch(self.session, f"https://some-random-api.ml/lyrics?title={urllib.parse.quote_plus(title)}")
        else:
            await ctx.respond(embed=error_embed(ctx, self.bot.errors.no_song_lyrics))
            return
        if "lyrics" not in response_json:
            await ctx.respond(embed=error_embed(ctx, self.bot.errors.no_lyrics_found))
            return
        lyrics = response_json["lyrics"]
        if len(lyrics) > 4096:
            embedLyrics = lyrics[0:3696] + "..." + \
                f"Too long to show inside the embed, go to the [webpage]({next(iter(response_json['links'].values()))})"
        else:
            embedLyrics = lyrics
        embed = discord.Embed(
            title=f"Showing results for {response_json['title']} by {response_json['author']}",
            description=embedLyrics,
            color=0xFF00FF
        ).set_thumbnail(
            url=f"{next(iter(response_json['thumbnail'].values()))}"
        ).set_footer(
            text=ctx.author.name + "#" + ctx.author.discriminator,
            icon_url=ctx.user.display_avatar.url
        )
        await ctx.respond(embed=embed)

    @slash_command(guild_ids=server_array)
    async def pos_remove(self, ctx: discord.ApplicationContext, position: int, playlist: bool = False):
        """Removes a song [or playlist if selected] from the queue by its position"""
        state = self.voice_state_manager.get_raw_voice_state(ctx)
        if not state or state.disconnected or not state.voice_client or not state.voice_client.is_connected():
            await ctx.respond(embed=error_embed(ctx, self.bot.errors.not_playing))
            return

        if not playlist:
            if 1 <= position <= len(state.queue):
                song_to_remove = state.queue[position-1]
                state.queue._queue.remove(song_to_remove)
                if song_to_remove.playlist:
                    song_to_remove.playlist.tracks.remove(song_to_remove)
                await ctx.respond(embed=info_embed(ctx, f"**Removed {song_to_remove.queue_field} from the queue**"))
            else:
                await ctx.respond(embed=error_embed(ctx, self.bot.errors.invalid_position))
        else:
            if 1 <= position <= len(state.queue.playlists):
                playlist_to_remove = state.queue.playlists[position-1]
                for song in playlist_to_remove.tracks:
                    try:
                        state.queue._queue.remove(song)
                    except Exception:
                        logger.exception("Error removing song from queue")
                del state.queue.playlists[position-1]
                await ctx.respond(embed=info_embed(ctx, description=f"**Removed {playlist_to_remove.queue_field} from the queue**"))
            else:
                await ctx.respond(embed=error_embed(ctx, self.bot.errors.invalid_position))

    @slash_command(guild_ids=server_array)
    async def remove(self, ctx: discord.ApplicationContext, name: str, playlist: bool = False, top: bool = False):
        """Removes a song [or playlist if selected] from the queue by its name"""
        state = self.voice_state_manager.get_raw_voice_state(ctx)
        if not state or state.disconnected or not state.voice_client or not state.voice_client.is_connected():
            await ctx.respond(embed=error_embed(ctx, self.bot.errors.not_playing))
            return
        if top:
            item_to_remove = state.queue.search_queue(
                name, playlist=playlist, top=True)[2]
            if playlist:
                for song in item_to_remove.tracks:
                    try:
                        state.queue._queue.remove(song)
                    except Exception:
                        logger.exception("Error removing song from queue")
                state.queue.playlists.remove(item_to_remove)
            else:
                state.queue._queue.remove(item_to_remove)
                if item_to_remove.playlist:
                    item_to_remove.playlist.tracks.remove(item_to_remove)
            await ctx.respond(embed=info_embed(ctx, description=f"**Removed {item_to_remove.queue_field} from the queue**"))
            del item_to_remove
        else:
            matches = state.queue.search_queue(
                name, playlist=playlist, top=False)
            await ctx.respond("** **", view=DropdownView(matches, playlist, state))

    @slash_command(guild_ids=server_array)
    async def play(self, ctx: discord.ApplicationContext, query: str, *, flags: Option(str, description="-n: Queues on top, -j: Queues on top and skips current song, -p: Queues a playlist, -s: Shuffles", required=False), filter: Option(str, description="Appends filter text to search spotify songs on youtube", required=False)):
        """Plays you a song!"""
        await ctx.defer()
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.respond(embed=error_embed(ctx, self.bot.errors.author_not_connected))
            return
        if ctx.guild.voice_client is None:
            voice_client = await ctx.author.voice.channel.connect()
            await ctx.respond(embed=Embed(title="Chizuru", color=0xFF00FF).add_field(name=f"{ctx.guild.name}", value=f"Joined <#{ctx.author.voice.channel.id}> and bound to <#{ctx.channel.id}>"))
        elif ctx.guild.voice_client.channel is None:
            voice_client = ctx.guild.voice_client
            await voice_client.move_to(ctx.author.voice.channel)
        elif ctx.guild.voice_client.channel.id == ctx.guild.voice_client.channel.id:
            voice_client = ctx.guild.voice_client
        elif len(ctx.guild.voice_client.channel.members) <= 1:
            voice_client = ctx.guild.voice_client
            await voice_client.move_to(ctx.author.voice.channel)
        else:
            await ctx.respond(embed=error_embed(ctx, self.bot.errors.connected_to_another_voice))
            return
        voice_state = self.voice_state_manager.get_voice_state(
            ctx, voice_client)
        if flags:
            flags = flags.split()
        else:
            flags = []
        if "open.spotify.com" in query:
            item_type, item_id = parse_spotify_url(query)
            data = parse_data(get_item_data(
                self.sp, item_type, item_id), item_type)
            data.update({"filter": filter})
            if item_type == 'album' or item_type == 'playlist':
                playlist = SpotifyPlaylist(ctx, data)
                voice_state.queue.insert(playlist, playlist=True, flags=flags)
                if "-l" in flags:
                    await ctx.channel.send("Queue looping has been turned on")
                if "-j" in flags and voice_state.voice_client.is_playing():
                    await self.skip(self, ctx)
                await ctx.respond(embed=playlist.queue_embed)
            else:
                song = SpotifySearch(ctx, data)
                voice_state.queue.insert(song, playlist=False, flags=flags)
                if "-l" in flags:
                    await ctx.channel.send("Song looping has been turned on")
                if "-j" in flags and voice_state.voice_client.is_playing():
                    await self.skip(self, ctx)
                await ctx.respond(embed=song.queue_embed)
        elif re.match(r'(?:https?:\/\/|\/\/)?(?:(?:www\.|music\.|m\.)?youtube(?:-nocookie)?\.com\/(?:(?:vi?|e|embed)\/([\w-]{11})|(?:watch|embed|attribution_link)?\?\S*?(?:(?<=\?v=|&v=)|(?<=\?vi=|&vi=))([\w-]{11}))|youtu\.be\/(?:([\w-]{11})(?!\S*v=)|\S*?(?:&v=|\?v=)([\w-]{11})))(?:[^\w-]\S*)?$', query):
            parsed_url = dict(parse.parse_qsl(parse.urlsplit(query).query))
            if "list" in parsed_url and "-p" in flags:
                partial = functools.partial(
                    YTDLSource.ytdl.extract_info, parsed_url['list'], download=False, process=True)
                data = await self.bot.loop.run_in_executor(None, partial)
                playlist = YoutubePlaylist(ctx, data)
                voice_state.queue.insert(playlist, playlist=True, flags=flags)
                if "-l" in flags:
                    await ctx.channel.send("Queue looping has been turned on")
                await ctx.respond(embed=playlist.queue_embed)
            partial = functools.partial(
                YTDLSource.ytdl.extract_info, query, download=False, process=True)
            try:
                data = await self.bot.loop.run_in_executor(None, partial)
            except Exception:
                logger.exception("Error extracting youtube data")
                await ctx.respond("This track is age restricted, skipping")

            if 'entries' in data:
                song = YoutubeSearch(ctx, data['entries'][0])
            else:
                song = YoutubeSong(ctx, data)
            voice_state.queue.insert(song, playlist=False, flags=flags)
            if "-l" in flags:
                await ctx.channel.send("Song looping has been turned on")
            if "-j" in flags and voice_state.voice_client.is_playing():
                await self.skip(self, ctx)
            await ctx.respond(embed=song.queue_embed)
        elif "youtube.com/playlist" in query:
            partial = functools.partial(
                YTDLSource.ytdl.extract_info, query, download=False, process=True)
            try:
                data = await self.bot.loop.run_in_executor(None, partial)
            except Exception:
                logger.exception("Error extracting youtube data")
                await ctx.respond(embed=error_embed(ctx, self.bot.errors.query_processing_fail))
            playlist = YoutubePlaylist(ctx, data)
            voice_state.queue.insert(playlist, playlist=True, flags=flags)
            if "-l" in flags:
                await ctx.channel.send("Queue looping has been turned on")
            if "-j" in flags and voice_state.voice_client.is_playing():
                await self.skip(self, ctx)
            await ctx.respond(embed=playlist.queue_embed)
        elif "https://" in query or "https://" in query:
            await ctx.respond(embed=error_embed(ctx, self.bot.errors.unrecognized_link))
        else:
            partial = functools.partial(
                YTDLSource.ytdl.extract_info, query, download=False, process=True)
            try:
                data = await self.bot.loop.run_in_executor(None, partial)
            except Exception:
                logger.exception("Error extracting search data")
                await ctx.respond(embed=error_embed(ctx, self.bot.errors.query_processing_fail))
                return
            if 'entries' in data:
                song = YoutubeSearch(ctx, data['entries'][0], query=query)
            else:
                song = YoutubeSearch(ctx, data, query=query)
            voice_state.queue.insert(song, playlist=False, flags=flags)
            if "-l" in flags:
                await ctx.channel.send("Song looping has been turned on")
            if "-j" in flags and voice_state.voice_client.is_playing():
                await self.skip(self, ctx)
            await ctx.respond(embed=song.queue_embed)
        if "-s" in flags:
            await self.shufflequeue(self, ctx)

    @slash_command(guild_ids=server_array)
    async def disconnect(self, ctx: discord.ApplicationContext):
        """Disconnects from the joined VC"""
        if ctx.guild.voice_client is None or ctx.guild.voice_client.channel is None:
            await self.voice_state_manager.remove_voice_state(ctx)
            await ctx.respond("**Disconnected successfully**")
            return
        if not ctx.author.voice or not ctx.author.voice.channel or ctx.author.voice.channel.id != ctx.guild.voice_client.channel.id:
            await ctx.respond(embed=error_embed(ctx, f"**Please connect to <#{ctx.guild.voice_client.channel.id}> before using this command**"), ephemeral=True)
            return
        await self.voice_state_manager.remove_voice_state(ctx)
        await ctx.respond("**Disconnected successfully**")

    @slash_command(guild_ids=server_array)
    async def skip(self, ctx: discord.ApplicationContext):
        """Skips to the next song"""
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.respond(embed=error_embed(ctx, self.bot.errors.author_not_connected), ephemeral=True)
            return
        state = self.voice_state_manager.get_raw_voice_state(ctx)
        if not state or not state.voice_client.is_connected or state.song is None:
            await ctx.respond(embed=error_embed(ctx, self.bot.errors.not_playing), ephemeral=True)
            return
        state.song_loop = False
        state.skip()
        await ctx.respond(embed=info_embed(ctx, "**Skipped**"))

    @slash_command(guild_ids=server_array)
    async def nowplaying(self, ctx: discord.ApplicationContext):
        """Shows the song that's being played at the moment"""
        state = self.voice_state_manager.get_raw_voice_state(ctx)
        if state and state.song and state.is_playing and not state.disconnected:
            await ctx.respond(embed=state.song.song_embed)
        else:
            await ctx.respond(embed=error_embed(ctx, self.bot.errors.not_playing))

    @slash_command(guild_ids=server_array)
    async def shufflequeue(self, ctx: discord.ApplicationContext):
        """Shuffles the queue"""
        state = self.voice_state_manager.get_raw_voice_state(ctx)
        if not state or state.disconnected or not state.voice_client or not state.voice_client.is_connected():
            await ctx.respond(embed=error_embed(ctx, self.bot.errors.not_playing))
            return
        random.shuffle(state.queue._queue)
        await ctx.respond(embed=info_embed(ctx, "Your queue has been shuffled"))

    @slash_command(guild_ids=server_array)
    async def queue(self, ctx: discord.ApplicationContext, page: int = 1, playlists: bool = False):
        """Shows the queue"""
        state = self.voice_state_manager.get_raw_voice_state(ctx)
        if not state or state.disconnected or not state.voice_client or not state.voice_client.is_connected():
            await ctx.respond(embed=error_embed(ctx, self.bot.errors.not_playing))
            return
        await ctx.defer()
        tracks = []
        if playlists:
            tracks = state.queue.playlists
            if len(tracks) == 0:
                await ctx.respond(embed=error_embed(ctx, self.bot.errors.no_playlists))
                return
            num_songs = len(tracks)
            items_per_page = 10
            pages = math.ceil(num_songs / items_per_page)
            if not (1 <= page <= pages):
                await ctx.respond(embed=error_embed(ctx, self.bot.errors.improper_page))
                return
            start = (page - 1) * items_per_page
            end = start + items_per_page
            queue = {}
            for i, song in enumerate(tracks[start:end], start=start):
                queue[f"{i+1}."] = song.queue_field

            embed = (discord.Embed(title=f"Queue: {num_songs} playlists", color=0xFF00FF)
                     .set_footer(text=f"Viewing page {page}/{pages}"))
            for title, description in queue.items():
                value = (f"**{title}**"+" "+description)
                if len(value) >= 1023:
                    value = value[:1000]+'...'
                embed.add_field(
                    name='\u200b', value=value, inline=False)
            await ctx.respond(embed=embed)
            return

        for item in state.queue:
            tracks.append(item)

        num_songs = len(tracks)

        if num_songs <= 0:
            if state.song:
                embed = (discord.Embed(
                    title=f"Queue: {0} tracks", color=0xFF00FF))
                embed.add_field(
                    name='\u200b', value=f"**Now Playing** {state.song.queue_field}", inline=False)
                await ctx.respond(embed=embed)
            else:
                await ctx.respond(embed=error_embed(ctx, self.bot.errors.empty_queue))

        else:
            items_per_page = 10
            pages = math.ceil(num_songs / items_per_page)
            if not (1 <= page <= pages):
                await ctx.respond(embed=error_embed(ctx, self.bot.errors.improper_page))
                return
            start = (page - 1) * items_per_page
            end = start + items_per_page

            queue = {}
            if state.song and state.voice_client.is_playing():
                if page == 1:
                    queue["Now Playing "] = state.song.queue_field
                    for i, song in enumerate(tracks[start:end], start=start):
                        if song is None:
                            continue
                        queue[f"{i+1}."] = song.queue_field
                else:
                    for i, song in enumerate(tracks[start:end], start=start):
                        if song is None:
                            continue
                        queue[f"{i+1}."] = song.queue_field
            else:
                for i, song in enumerate(tracks[start:end], start=start):
                    if song is None:
                        continue
                    queue[f"{i+1}."] = song.queue_field

            embed = (discord.Embed(title=f"Queue: {num_songs} tracks ({parse_duration(state.queue.total_time())})", color=0xFF00FF)
                     .set_footer(text=f"Viewing page {page}/{pages}"))
            for title, description in queue.items():
                value = (f"**{title}**"+" "+description)
                if len(value) >= 1023:
                    value = value[:1000]+'...'
                embed.add_field(
                    name='\u200b', value=value, inline=False)
            await ctx.respond(embed=embed)

    @slash_command(guild_ids=server_array)
    async def volume(self, ctx: discord.ApplicationContext, volume: int):
        """Set the volume for subsequent tracks"""
        if not 1 <= volume <= 100:
            await ctx.respond(embed=error_embed(ctx, self.bot.errors.improper_volume))
            return
        state = self.voice_state_manager.get_raw_voice_state(ctx)
        if state and not state.disconnected:
            state.volume = volume/100
            await ctx.respond(embed=info_embed(ctx, f"Set the volume to **{volume}%**"))
            return
        else:
            await ctx.respond(embed=error_embed(ctx, self.bot.errors.not_connected_to_voice))

    @slash_command(guild_ids=server_array)
    async def loop(self, ctx: discord.ApplicationContext, song: bool = False):
        """Loop the Queue or Song (if song is set to True)"""
        state = self.voice_state_manager.get_raw_voice_state(ctx)
        if not state or state.disconnected or not state.voice_client or not state.voice_client.is_connected():
            await ctx.respond(embed=error_embed(ctx, self.bot.errors.not_playing))
            return
        if song:
            state.song_loop = not state.song_loop
            if state.song_loop:
                await ctx.respond("Song looping has been turned **ON**")
            else:
                await ctx.respond("Song looping has been turned **OFF**")
        else:
            state.queue_loop = not state.queue_loop
            if state.queue_loop:
                await ctx.respond("Queue looping has been turned **ON**")
            else:
                await ctx.respond("Queue looping has been turned **OFF**")

    @slash_command(guild_ids=server_array)
    async def move(self, ctx: discord.ApplicationContext, position: int, new: int):
        """Move song from position to new and shifts to right"""
        state = self.voice_state_manager.get_raw_voice_state(ctx)
        if not state or state.disconnected or not state.voice_client or not state.voice_client.is_connected():
            await ctx.respond(embed=error_embed(ctx, self.bot.errors.not_playing))
            return
        if 1 <= position <= len(state.queue) and 1 <= new <= len(state.queue) and position != new:
            track_to_move = state.queue[position-1]
            state.queue._queue.remove(track_to_move)
            state.queue._queue.insert(new-1, track_to_move)
            embed = info_embed(ctx, 
                description=f"**Moved {track_to_move.queue_field} from `{position}` to `{new}`**", color=0xFF00FF)
            await ctx.respond(embed=embed)
            return
        else:
            await ctx.respond(embed=error_embed(ctx, self.bot.errors.improper_position))
            return

    # @slash_command(guild_id=server_array)
    # async def save(self, ctx: discord.ApplicationContext, title: str):
    #     """Save the current queue as a playlist"""
    #     pass
    @lyrics.before_invoke
    @pos_remove.before_invoke
    @remove.before_invoke
    @skip.before_invoke
    @queue.before_invoke
    @shufflequeue.before_invoke
    @volume.before_invoke
    @loop.before_invoke
    @move.before_invoke
    async def check_for_vc(self, ctx: ApplicationContext):
        async def check():
            if ctx.guild.voice_client is None or ctx.guild.voice_client.channel is None:
                await ctx.respond(embed=error_embed(ctx, "I'm not connected to a voice channel yet. Use /play to connect to a voice channel."), ephemeral=True)
                return False
            if not ctx.author.voice or not ctx.author.voice.channel or ctx.author.voice.channel.id != ctx.guild.voice_client.channel.id:
                await ctx.respond(embed=error_embed(ctx, f"**Please connect to <#{ctx.guild.voice_client.channel.id}> before using this command**"), ephemeral=True)
                return False
            return True
        if await check():
            return True
        else:
            raise NotVoiceChannel(ctx, "User not in same channel as bot")


async def fetch(session: aiohttp.ClientSession, url, **kwargs):
    """
    Uses aiohttp to make http get requests
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/84.0.4147.89 Safari/537.36",
        "Authorization": "Bearer mHZETd5-trJB6G49dEY4TJdsvzNuNHK63h_BRRAFm_QEXyLgSthFH7sIiNFZeOUT"
    }
    async with session.get(url, headers=headers, **kwargs) as resp:
        return await resp.json()
