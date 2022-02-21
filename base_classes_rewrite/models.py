import functools
import asyncio
import discord
from discord import Embed
import yt_dlp
import traceback


class URLNotFound(Exception):
    pass


class YTDLError(Exception):
    pass


class YTDLSource(discord.PCMVolumeTransformer):
    YTDL_OPTIONS = {
        'format': 'bestaudio/best',
        'extractaudio': True,
        'audioformat': 'mp3',
        'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
        'restrictfilenames': True,
        'noplaylist': True,
        'nocheckcertificate': True,
        'ignoreerrors': False,
        'logtostderr': False,
        'quiet': True,
        'no_warnings': True,
        'default_search': 'auto',
        'source_address': '0.0.0.0',
        'extract_flat': 'in_playlist'
    }
    FFMPEG_OPTIONS_BEFORE = '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'
    FFMPEG_OPTIONS = '-vn'  # -ignore_unknown -sn -dn'
    ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)

    @classmethod
    async def parse_query(cls, query: str, loop=None):
        loop = loop or asyncio.get_event_loop()
        partial = functools.partial(
            cls.ytdl.extract_info, query, download=False, process=True)
        try:
            data = await loop.run_in_executor(None, partial)
        except Exception as e:
            print(f"error: {e}")
        if not data:
            raise YTDLError(f"Couldn\'t find anything that matches {query}")
        extractor = data.get('extractor')
        if 'youtube' in extractor:
            if data.get('_type') == "playlist":
                if len(data.get('entries')) <= 1:
                    return data.get('entries')[0], 'url', False
                else:
                    return data, 'list', False
            elif data.get('_type') == 'url':
                return data, 'url', True
            else:
                return data, 'url', True
        elif 'soundcloud' in extractor:
            if data.get('_type') == "playlist":
                if len(data.get('entries')) <= 1:
                    return data.get('entries')[0], 'url', False
                else:
                    return data, 'list', False
            elif data.get('_type') == 'url':
                return data, 'url', True
            else:
                if 'url' in data:
                    return data, 'url', True
                else:
                    raise YTDLError(data.get('_type'))


class YoutubeSearch:
    """The search result from a youtube search"""

    def __init__(self, ctx, data: dict, playlist=None, query=None):
        self.data = data
        self.ctx = ctx
        self.requester = ctx.author
        self.guild = ctx.guild

        self.title: str = data.get('title')
        self.query = query or self.title
        self.id = data.get('id')
        self.duration = self.parse_duration(int(data.get('duration')))
        self.duration_int = int(data.get('duration'))
        self.views = data.get('view_count') or 'hidden'
        self.uploader = data.get('uploader')
        self.webpage_url = f"https://www.youtube.com/watch?v={self.id}"
        self.is_playlist = False
        self.is_processed = False
        self.playlist = playlist

    @property
    def queue_field(self):
        return f"[{self.title}]({self.webpage_url}) - (𝘙𝘦𝘲𝘶𝘦𝘴𝘵𝘦𝘥 𝘣𝘺 <@{self.requester.id}>)"

    @property
    def track_description(self):
        return f"{self.title} - {self.uploader}"

    @property
    def queue_embed(self) -> Embed:
        return Embed(title="Queue", description=f"Added [{self.title}]({self.webpage_url}) to the queue", color=0xFF00FF)

    @property
    def song_embed(self) -> Embed:
        try:
            self.views = "{:,}".format(self.views)
        except Exception:
            pass
        return discord.Embed(
            title="Now Playing",
            color=0xFF00FF,
            description=f"[{self.title}]({self.webpage_url})"
        ).add_field(
            name="Uploader",
            value=f"" + self.uploader
        ).add_field(
            name="Duration",
            value=f"{self.duration}"
        ).add_field(
            name="Views",
            value=f"{self.views}"
        ).add_field(
            "Requested by",
            value=f"{self.requester.mention}"
        )

    async def create_song(self, loop=None, volume: float = 1.0):
        loop = loop or asyncio.get_event_loop()
        partial = functools.partial(
            YTDLSource.ytdl.extract_info, self.webpage_url, download=False, process=True)
        try:
            data = await asyncio.get_event_loop().run_in_executor(None, partial)
            return YoutubeSong(self.ctx, data, volume)
        except Exception as e:
            traceback.print_exc()
            raise e

    @staticmethod
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


class YoutubeSong(YoutubeSearch):
    """A processed youtube song"""

    def __init__(self, ctx, data: dict, volume: float = 1.0):
        super().__init__(ctx, data)
        self.url = data.get('url')
        self.uploader_url = data.get('uploader_url')
        self.is_playlist = False
        self.is_processed = True
        self.volume = volume
        self.thumbnail = data.get('thumbnail')

    @property
    def song_embed(self) -> Embed:
        try:
            self.views = "{:,}".format(self.views)
        except Exception:
            pass
        if not hasattr(self, 'thumbnail'):
            self.thumbnail = "https://media.discordapp.net/attachments/779658216501018634/894193494137110549/chizuruBanner.png"
        return discord.Embed(
            title="Now Playing",
            color=0xFF00FF,
            description=f"[{self.title}]({self.webpage_url})"
        ).set_thumbnail(
            url=self.thumbnail
        ).add_field(
            name="Uploader",
            value=f"[{self.uploader}]({self.uploader_url})"
        ).add_field(
            name="Duration",
            value=f"{self.duration}"
        ).add_field(
            name="Views",
            value=f"{self.views}"
        ).add_field(
            name="Requested by",
            value=f"{self.requester.mention}"
        )

    def create_source(self):
        return discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(self.url, options=YTDLSource.FFMPEG_OPTIONS, before_options=YTDLSource.FFMPEG_OPTIONS_BEFORE), self.volume)


class SpotifySearch:
    def __init__(self, ctx, data: dict, playlist=None):
        self.data = data
        self.ctx = ctx
        self.requester = ctx.author
        self.guild = ctx.guild
        self.name = data.get('name')
        self.webpage_url = data.get('webpage_url')
        self.duration_int = data.get('duration')
        artists = ""
        for artist in data.get('artists'):
            artists += (artist + " ")
        self.artists = data.get('artists')
        self.query = f"{artists.strip()} - {data.get('name')} {data.get('filter') if data.get('filter') else 'Lyrics'}".replace(
            ":", "").replace("\"", "").strip()
        self.is_playlist = False
        self.is_processed = False
        self.playlist = playlist

    @property
    def title(self):
        return self.name

    @property
    def track_description(self):
        return f"{self.name} - {', '.join(self.artists)}"

    @property
    def queue_field(self):
        return f"[{self.name}]({self.webpage_url}) - (𝘙𝘦𝘲𝘶𝘦𝘴𝘵𝘦𝘥 𝘣𝘺 <@{self.requester.id}>)"

    @property
    def queue_embed(self) -> Embed:
        return Embed(title="Queue", description=f"Added [{self.name}]({self.webpage_url}) to the queue", color=0xFF00FF)

    @property
    def song_embed(self) -> Embed:
        return discord.Embed(
            title="Now Playing",
            color=0xFF00FF,
            description=f"[{self.name}]({self.url})"
        ).add_field(
            name="Duration",
            value=self.duration,
        ).add_field(
            name="Artist(s)",
            value="" + ", ".join(self.artists),
        ).add_field(
            name="Requested by",
            value=f"{self.requester.mention}"
        )

    async def create_song(self, loop=None, volume: float = 1.0):
        loop = loop or asyncio.get_event_loop()
        partial = functools.partial(
            YTDLSource.ytdl.extract_info, self.query, download=False, process=True)
        data = await loop.run_in_executor(None, partial)
        youtube_url = f"https://www.youtube.com/watch?v={data.get('entries')[0].get('id')}"
        partial = functools.partial(
            YTDLSource.ytdl.extract_info, youtube_url, download=False, process=True)
        try:
            data = await asyncio.get_event_loop().run_in_executor(None, partial)
            return SpotifySong(self.ctx, self.data, data, volume)

        except Exception as e:
            traceback.print_exc()
            raise e

    @staticmethod
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


class SpotifySong(SpotifySearch):
    def __init__(self, ctx, spotify_data, data: dict, volume: float = 1.0):
        super().__init__(ctx, spotify_data)
        self.spotify_data = spotify_data
        self.url = data.get('url')
        self.youtube_url = data.get('webpage_url')
        self.youtube_title = data.get('title')
        self.duration = self.parse_duration(int(data.get('duration')))
        self.volume = volume
        self.is_playlist = False
        self.is_processed = True
        self.thumbnail = data.get('thumbnail')

    @property
    def song_embed(self) -> Embed:
        if not hasattr(self, 'thumbnail'):
            self.thumbnail = "https://media.discordapp.net/attachments/779658216501018634/894193494137110549/chizuruBanner.png"
        embed = discord.Embed(
            title="Now Playing",
            color=0xFF00FF,
            description=f"[{self.name}]({self.webpage_url})"
        ).set_thumbnail(
            url=self.thumbnail
        ).add_field(
            name="Duration",
            value=self.duration,
        ).add_field(
            name="Artist(s)",
            value="" + ", ".join(self.artists),
        ).add_field(
            name="Requested by",
            value=f"{self.requester.mention}"
        ).add_field(
            name="Playback URL",
            value=f"[{self.youtube_title}]({self.youtube_url})"
        )
        if self.spotify_data.get("filter"):
            embed.add_field(
                name="Filter",
                value=self.spotify_data.get("filter")
            )
        return embed

    def create_source(self):
        return discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(self.url, options=YTDLSource.FFMPEG_OPTIONS, before_options=YTDLSource.FFMPEG_OPTIONS_BEFORE), self.volume)


class YoutubePlaylist:
    def __init__(self, ctx, data: dict):
        self.ctx = ctx
        self.is_playlist = True
        self.tracks: list[YoutubeSearch] = [YoutubeSearch(
            ctx, entry, playlist=self) for entry in data.get('entries')]
        self.title = data.get('title')
        self.uploader = data.get('uploader')
        self.uploader_url = data.get('uploader_url')
        self.webpage_url = data.get('webpage_url')

    @property
    def queue_field(self):
        return f"[{self.title}]({self.webpage_url}) [{len(self.tracks)}] - (𝘙𝘦𝘲𝘶𝘦𝘴𝘵𝘦𝘥 𝘣𝘺 <@{self.ctx.author.id}>)"

    @property
    def queue_embed(self) -> Embed:
        return Embed(title="Queue", color=0xFF00FF).add_field(name=f"{self.ctx.guild.name}", value=f"Added [{self.title}]({self.webpage_url}) to queue with {len(self.tracks)} songs")


class SpotifyPlaylist:
    def __init__(self, ctx, data: dict):
        filter = data.get("filter")
        self.tracks = []
        for track in data.get('tracks'):
            track.update({"filter": filter})
            self.tracks.append(SpotifySearch(ctx, track, playlist=self))
        self.name = data.get('name')
        self.webpage_url = data.get('webpage_url')
        self.is_playlist = True
        self.ctx = ctx

    @property
    def title(self):
        return self.name

    @property
    def playlist_length(self):
        return len(self.tracks)

    @property
    def queue_field(self):
        return f"[{self.name}]({self.webpage_url}) [{len(self.tracks)}] - (𝘙𝘦𝘲𝘶𝘦𝘴𝘵𝘦𝘥 𝘣𝘺 <@{self.ctx.author.id}>)"

    @property
    def queue_embed(self) -> Embed:
        return Embed(title="Queue", color=0xFF00FF).add_field(name=f"{self.ctx.guild.name}", value=f"Added [{self.name}]({self.webpage_url}) to queue with {len(self.tracks)} songs")


# class SoundcloudSong:
#     def __init__(self, ctx, data:dict, volume:float=1.0):
#         pass

#     @property
#     def queue_embed(self) -> Embed:
#         pass

#     @property
#     def song_embed(self) -> Embed:
#         pass


# class SoundcloudPlaylist:
#     def __init__(self, ctx, data:dict):
#         self.tracks:list[SoundcloudSong] = []
#         pass

#     @property
#     def queue_embed(self) -> Embed:
#         pass
