from asyncio.events import AbstractEventLoop
import itertools
import urllib
import aiohttp
import discord
import asyncio
from discord import voice_client
from discord.commands.context import ApplicationContext
from discord.ext import commands
import random
from async_timeout import timeout
from base_classes_rewrite.models import *
import traceback
import logging
from typing import Union
from fuzzywuzzy import process

logging.basicConfig(filename='./chizuru_bot.log', level=logging.ERROR,
                    format='%(asctime)s %(levelname)s %(name)s %(message)s')
logger = logging.getLogger(__name__)


class URLNotFound(Exception):
    pass


class YTDLError(Exception):
    pass


class SongQueue(asyncio.Queue):
    def __init__(self, voice_handler, queue_loop=False):
        super().__init__()
        self.links_dict = {}
        self.queue_loop = queue_loop
        self.playlists = []
        self.voice_handler = voice_handler

    def search_queue(self, pattern, playlist=False, top=False):
        if playlist:
            names = {playlist: playlist.title for playlist in self.playlists}
        else:
            names = {track: track.title for track in self._queue}
        if top:
            return process.extractOne(pattern, names)
        return process.extract(pattern, names)

    def __getitem__(self, item):
        if isinstance(item, slice):
            return list(itertools.islice(self._queue, item.start, item.stop, item.step))
        else:
            return self._queue[item]
    
    def total_time(self):
        duration = 0
        for song in self._queue:
            duration += song.duration_int
        return duration

    def insert(self, item: Union[YoutubeSearch, YoutubePlaylist, SpotifySearch, SpotifyPlaylist, YoutubeSong, SpotifySong], playlist=False, flags=None):
        flags = flags if flags else []
        left = "-n" in flags or "-j" in flags
        shuffle = "-s" in flags
        loop = "-l" in flags
        if playlist and item.is_playlist:
            tracks = item.tracks.copy()
            if shuffle:
                random.shuffle(tracks)
            if loop:
                self.queue_loop = True
            if left:
                self._queue.extendleft(tracks)
                self.playlists.insert(0, item)
            else:
                self._queue.extend(tracks)
                self.playlists.append(item)

        else:
            if loop:
                self.voice_handler.song_loop = True
            if left:
                self._queue.appendleft(item)
            else:
                self._queue.append(item)
        self._wakeup_next(self._getters)

    def cleanup_track(self, item: Union[YoutubeSearch, YoutubePlaylist, SpotifySearch, SpotifyPlaylist, YoutubeSong, SpotifySong]):
        if self.queue_loop:
            self._queue.append(item)
            self._wakeup_next(self._getters)
        else:
            if item.playlist:
                item.playlist.tracks.remove(item)
                if len(item.playlist.tracks) == 0:
                    self.playlists.remove(item.playlist)

    def remove_pos(self, pos: int):
        del self._queue[pos]

    def __iter__(self):
        return self._queue.__iter__()

    def __len__(self):
        return self.qsize()

    def clear(self):
        self._queue.clear()

    def shuffle(self):
        random.shuffle(self._queue)

    def remove(self, index: int):
        del self._queue[index]

    async def put_flags(self, song, flags):
        if "-n" or "-j" in flags:
            self.putleft(song)
        else:
            await self.put(song)


async def fetch(session: aiohttp.ClientSession, url, **kwargs):
    """
    Uses aiohttp to make http GET requests
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/84.0.4147.89 Safari/537.36",
        "Authorization": "Bearer mHZETd5-trJB6G49dEY4TJdsvzNuNHK63h_BRRAFm_QEXyLgSthFH7sIiNFZeOUT"
    }
    async with session.get(url, headers=headers, **kwargs) as resp:
        return await resp.json()


class Buttons(discord.ui.View):
    def __init__(self, voice_handler, song, response_json=None, timeout=180):
        super().__init__(timeout=timeout)
        self.resume_button = ResumeButton(self, voice_handler, song)
        self.pause_button = PauseButton(self, voice_handler, song)
        self.add_item(SkipButton(self, voice_handler, song))
        self.response_json = response_json
        if response_json and "lyrics" in response_json:
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
            )
            self.add_item(LyricsButton(embed))
        if voice_handler.voice_client.is_paused():
            self.add_item(self.resume_button)
        else:
            self.add_item(self.pause_button)

    async def disable(self, interaction):
        for i in self.children:
            i.disabled = True
        await interaction.message.edit(view=self)

    async def disable_from_message(self, message):
        for i in self.children:
            i.disabled = True
        await message.edit(view=self)


class LyricsButton(discord.ui.Button):
    def __init__(self, embed):
        super().__init__(style=discord.ButtonStyle.green, label="Lyrics")
        self.embed = embed

    async def callback(self, interaction: discord.Interaction):
        await interaction.channel.send(embed=self.embed)


async def is_manager(ctx: discord.Interaction, condition: bool):
    if condition:
        if not ctx.guild.get_role(801326058409426995) in ctx.user.roles:
            await ctx.response.send_message(
                embed=discord.Embed(
                    title="Error",
                    description="**You don't have the permissions for that.**"
                ), ephemeral=True
            )
            return False
        else:
            return True
    else:
        return True


def error_embed(ctx: discord.Interaction, error_message):
    return Embed(title="Chizuru", color=0xFF00FF).add_field(name=ctx.guild.name, value=error_message)


async def check_for_vc(ctx: discord.Interaction):
    async def check():
        async def respond(*args, **kwargs):
            func = ctx.followup.send if ctx.response.is_done() else ctx.response.send_message
            await func(*args, **kwargs)
        if ctx.guild.voice_client is None or ctx.guild.voice_client.channel is None:
            await respond(embed=error_embed(ctx, "I'm not connected to a voice channel yet. Use /play to connect to a voice channel."), ephemeral=True)
            return False
        if not ctx.user.voice or not ctx.user.voice.channel or ctx.user.voice.channel.id != ctx.guild.voice_client.channel.id:
            await respond(embed=error_embed(ctx, f"Please connect to <#{ctx.guild.voice_client.channel.id}> before using this command"), ephemeral=True)
            return False
        return True
    if await check():
        return True
    else:
        return False


class SkipButton(discord.ui.Button):
    def __init__(self, view: Buttons, voice_handler, song):
        super().__init__(style=discord.ButtonStyle.red, label="Skip")
        self.voice_handler = voice_handler
        self.buttons_view = view
        self.song = song

    async def callback(self, interaction: discord.Interaction):
        if not await check_for_vc(interaction):
            return
        if await is_manager(interaction, self.voice_handler.voice_client.channel.id == 750958821719015505):
            await self.buttons_view.disable(interaction)
            self.voice_handler.skip()
            self.buttons_view.stop()
            await interaction.channel.send(embed=discord.Embed(description=f"Skipped **[{self.song.title}]({self.song.webpage_url})**, requested by - <@{interaction.user.id}>", color=0xFF00FF))


class PauseButton(discord.ui.Button):
    def __init__(self, view: Buttons, voice_handler, song):
        super().__init__(style=discord.ButtonStyle.primary, label="Pause")
        self.voice_handler: VoiceHandler = voice_handler
        self.buttons_view = view
        self.song = song

    async def callback(self, interaction: discord.Interaction):
        if not await check_for_vc(interaction):
            return
        if await is_manager(interaction, self.voice_handler.voice_client.channel.id == 750958821719015505):
            self.voice_handler.voice_client.pause()
            await interaction.channel.send(embed=discord.Embed(description=f"**Paused** the player, requested by - <@{interaction.user.id}>", color=0xFF00FF))
            self.buttons_view.add_item(self.buttons_view.resume_button)
            self.buttons_view.remove_item(self.buttons_view.pause_button)
            await interaction.message.edit(view=self.buttons_view)


class ResumeButton(discord.ui.Button):
    def __init__(self, view: Buttons, voice_handler, song):
        super().__init__(style=discord.ButtonStyle.primary, label="Resume")
        self.voice_handler: VoiceHandler = voice_handler
        self.buttons_view = view
        self.song = song

    async def callback(self, interaction: discord.Interaction):
        if not await check_for_vc(interaction):
            return
        if await is_manager(interaction, self.voice_handler.voice_client.channel.id == 750958821719015505):
            self.voice_handler.voice_client.resume()
            await interaction.channel.send(embed=discord.Embed(description=f"**Resumed** the player, requested by - <@{interaction.user.id}>", color=0xFF00FF))
            self.buttons_view.remove_item(self.buttons_view.resume_button)
            self.buttons_view.add_item(self.buttons_view.pause_button)
            await interaction.message.edit(view=self.buttons_view)


class VoiceHandler:
    def __init__(self, bot: discord.Bot, ctx: ApplicationContext, voice_client: discord.VoiceClient):
        self.bot = bot
        self.ctx = ctx
        self.voice_client = voice_client
        self._disconnected = False
        self.next = asyncio.Event()
        self.voice_client_ready = asyncio.Event()
        self.no_members = asyncio.Event()
        self.wait_for_join = asyncio.Event()
        self.voice_client_ready.set()
        self._volume = 1
        self.queue = SongQueue(self)
        self.song_loop = False
        self.song: Union[YoutubeSearch, YoutubePlaylist,
                         SpotifySearch, SpotifyPlaylist, YoutubeSong, None] = None
        self.loop = bot.loop
        self.audio_player = self.loop.create_task(self.audio_player_task())
        self.session = aiohttp.ClientSession()

    def update_voice(self, voice_client):
        self.voice_client = voice_client
        self.voice_client_ready.set()

    async def no_members_task(self):
        while True:
            await self.no_members.wait()
            try:
                async with timeout(120):
                    await self.wait_for_join.wait()
            except asyncio.TimeoutError:
                if not self.disconnected and self.voice_client and self.voice_client.is_connected():
                    await self.ctx.channel.send(f"Disconnected due to inactivity")
                    await self.disconnect()
                    return
                await self.disconnect()
                return

    async def audio_player_task(self):
        while True:
            if self.disconnected:
                return
            self.next.clear()
            if self.voice_client:
                self.voice_client.stop()

            source = None
            if not self.song_loop:
                self.song = None
            while not source:
                if not self.song_loop or not self.song:
                    try:
                        async with timeout(120):
                            self.song = await self.queue.get()
                            self.queue.cleanup_track(self.song)
                    except asyncio.TimeoutError:
                        if not self.disconnected and self.voice_client and self.voice_client.is_connected():
                            await self.ctx.channel.send(f"Disconnected due to inactivity")
                        await self.disconnect()
                        return
                self.song.volume = self._volume
                if self.song.is_processed:
                    try:
                        source = self.song.create_source()
                    except Exception:
                        logger.exception("Error creating source")
                        if self.song:
                            title = self.song.title if hasattr(
                                self.song, "title") else self.song.name
                        else:
                            title = "None"
                        await self.ctx.channel.send(f"Track {title} not found, skipping")
                else:
                    try:
                        self.song = await self.song.create_song()
                    except Exception as e:
                        logger.exception("Error creating song")
                        await self.ctx.channel.send("<@522714407969488896>, <@291043355104641025>", embed=discord.Embed(description=f"I couldn't play `{(self.song.title if hasattr(self.song, 'title') else self.song.name)}` cus of `{str(e)}`\n\n**Note: This is very sus behaviour and has been logged**"))
                        continue
                    try:
                        source = self.song.create_source()
                    except Exception:
                        logger.exception("Error creating source")
                        await self.ctx.channel.send("Song not found, skipping")
            self.voice_client.play(source, after=self.play_next)
            try:
                response_json = await fetch(self.session, f"https://some-random-api.ml/lyrics?title={urllib.parse.quote_plus(self.song.title)}")
            except Exception:
                response_json = None
            try:
                view = Buttons(self, self.song,
                               response_json=response_json, timeout=None)
                last_message = await self.ctx.channel.send(embed=self.song.song_embed, view=view)
                await self.next.wait()
                await view.disable_from_message(last_message)
                view.stop()
                continue
            except Exception as e:
                logger.exception("Error playing song")
                await self.ctx.channel.send("<@522714407969488896>, <@291043355104641025>", embed=discord.Embed(description=f"I couldn't play this song cus of `{str(e)}`\n\n**Note: This is very sus behaviour and has been logged**"))

    def play_next(self, error: Exception):
        if error:
            logger.error(error.__traceback__)
        self.next.set()

    async def disconnect(self):
        self.disconnected = True
        self.voice_client_ready.clear()
        if self.voice_client:
            try:
                await self.voice_client.disconnect(force=True)
            except Exception:
                pass
        self.voice_client = None

    def update_context(self, ctx):
        self.ctx = ctx

    def reset(self, bot: discord.Bot, ctx: ApplicationContext, voice_client: discord.VoiceClient):
        self = self.__init__(bot, ctx, voice_client)

    def skip(self):
        self.voice_client.stop()

    @property
    def disconnected(self):
        return self._disconnected

    @disconnected.setter
    def disconnected(self, state: bool):
        self._disconnected = state

    @property
    def queue_loop(self):
        return self.queue.queue_loop

    @queue_loop.setter
    def queue_loop(self, value: bool):
        self.queue.queue_loop = value

    @property
    def volume(self):
        return self._volume

    @volume.setter
    def volume(self, value: float):
        self._volume = value

    @property
    def is_playing(self):
        return self.voice_client.is_playing()

    @property
    def is_ready(self):
        return self.voice_client_ready.is_set() and self.voice_client and self.voice_client.is_connected()


class VoiceStateManager:
    def __init__(self, bot: discord.Bot) -> None:
        self.bot = bot
        self.voice_states: dict[str, VoiceHandler] = {}

    def get_voice_state(self, ctx: ApplicationContext, voice_client) -> VoiceHandler:
        state: VoiceHandler = self.voice_states.get(str(ctx.guild_id))
        if state and not state.disconnected:
            state.update_voice(voice_client)
            return state
        else:
            self.voice_states[str(ctx.guild_id)] = VoiceHandler(
                self.bot, ctx, voice_client)
            return self.voice_states.get(str(ctx.guild_id))

    def update_voice_state(self, ctx: ApplicationContext, voice_client):
        self.voice_states[str(ctx.guild_id)] = VoiceHandler(
            self.bot, ctx, voice_client)

    async def remove_voice_state(self, ctx):
        state = self.voice_states.pop(str(ctx.guild_id), None)
        if state:
            await state.disconnect()

    def flush_voice_states(self):
        self.voice_states.clear()

    def get_raw_voice_state(self, ctx):
        return self.voice_states.get(str(ctx.guild.id))
