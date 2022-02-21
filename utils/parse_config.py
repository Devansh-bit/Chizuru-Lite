from attr import dataclass


@dataclass
class Config:
    debug_guilds: list
    bot_name: str
    version: str
    logging: dict
    embed_colour: str
    bot_owner_discord_ids: list
    database_name: str

@dataclass
class ErrorMessages:
    not_connected_to_voice: str
    connected_to_another_voice: str
    unrecognised_link: str
    query_processing_fail: str
    not_playing: str
    no_playlists: str
    empty_queue: str
    improper_page: str
    improper_volume: str
    improper_position: str
    author_not_connected: str
    error_embed_colour: str
    no_song_lyrics: str
    no_lyrics_found: str


