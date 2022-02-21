import sys
import spotipy
from spotipy import Spotify
from spotipy.oauth2 import SpotifyClientCredentials
import dotenv
dotenv.load_dotenv()


def fetch_tracks(sp: Spotify, item_type, url):
    """
    Fetches tracks from the provided URL.
    :param sp: Spotify client
    :param item_type: Type of item being requested for: album/playlist/track
    :param url: URL of the item
    :return Dictionary of song and artist
    """
    songs_list = []
    offset = 0

    if item_type == 'playlist':
        while True:
            items = sp.playlist_items(playlist_id=url),
            print(items[1])
            total_songs = items.get('total')
            for item in items['items']:
                track_info = item.get('track')
                track_album_info = track_info.get('album')

                track_num = track_info.get('track_number')
                spotify_id = track_info.get('id')
                track_name = track_info.get('name')
                track_artist = ", ".join([artist['name']
                                         for artist in track_info.get('artists')])

                if track_album_info:
                    track_album = track_album_info.get('name')
                    track_year = track_album_info.get('release_date')[
                        :4] if track_album_info.get('release_date') else ''
                    album_total = track_album_info.get('total_tracks')

                if len(item['track']['album']['images']) > 0:
                    cover = item['track']['album']['images'][0]['url']
                else:
                    cover = None

                if len(sp.artist(artist_id=item['track']['artists'][0]['uri'])['genres']) > 0:
                    genre = sp.artist(artist_id=item['track']['artists'][0]['uri'])[
                        'genres'][0]
                else:
                    genre = ""
                songs_list.append({"name": track_name, "artist": track_artist, "album": track_album, "year": track_year,
                                   "num_tracks": album_total, "num": track_num, "playlist_num": offset + 1,
                                   "cover": cover, "genre": genre, "spotify_id": spotify_id})
                offset += 1

            if total_songs == offset:
                break

    elif item_type == 'album':
        while True:
            album_info = sp.album(album_id=url)
            items = sp.album_tracks(album_id=url)
            total_songs = items.get('total')
            track_album = album_info.get('name')
            track_year = album_info.get('release_date')[
                :4] if album_info.get('release_date') else ''
            album_total = album_info.get('total_tracks')
            if len(album_info['images']) > 0:
                cover = album_info['images'][0]['url']
            else:
                cover = None
            if len(sp.artist(artist_id=album_info['artists'][0]['uri'])['genres']) > 0:
                genre = sp.artist(artist_id=album_info['artists'][0]['uri'])[
                    'genres'][0]
            else:
                genre = ""
            for item in items['items']:
                track_name = item.get('name')
                track_artist = ", ".join([artist['name']
                                         for artist in item['artists']])
                track_num = item['track_number']
                spotify_id = item.get('id')
                songs_list.append({"name": track_name, "artist": track_artist, "album": track_album, "year": track_year,
                                   "num_tracks": album_total, "num": track_num, "playlist_num": offset + 1,
                                   "cover": cover, "genre": genre, "spotify_id": spotify_id})
                offset += 1

            if total_songs == offset:
                break

    elif item_type == 'track':
        items = sp.track(track_id=url)
        track_name = items.get('name')
        album_info = items.get('album')
        track_artist = ", ".join([artist['name']
                                 for artist in items['artists']])
        if album_info:
            track_album = album_info.get('name')
            track_year = album_info.get('release_date')[
                :4] if album_info.get('release_date') else ''
            album_total = album_info.get('total_tracks')
        track_num = items['track_number']
        spotify_id = items['id']
        if len(items['album']['images']) > 0:
            cover = items['album']['images'][0]['url']
        else:
            cover = None
        if len(sp.artist(artist_id=items['artists'][0]['uri'])['genres']) > 0:
            genre = sp.artist(artist_id=items['artists'][0]['uri'])[
                'genres'][0]
        else:
            genre = ""
        songs_list.append({"name": track_name, "artist": track_artist, "album": track_album, "year": track_year,
                           "num_tracks": album_total, "num": track_num, "playlist_num": offset + 1,
                           "cover": cover, "genre": genre, "spotify_id": spotify_id})

    return songs_list


def sanitize(name, replace_with=''):
    """
    Removes some of the reserved characters from the name so it can be saved
    :param name: Name to be cleaned up
    :return string containing the cleaned name
    """
    clean_up_list = ["\\", "/", ":", "*", "?", "\"", "<", ">", "|", "\0", "$"]
    for x in clean_up_list:
        name = name.replace(x, replace_with)
    return name


def parse_spotify_url(url):
    """
    Parse the provided Spotify playlist URL and determine if it is a playlist, track or album.
    :param url: URL to be parsed
    :return tuple indicating the type and id of the item
    """
    if url.startswith("spotify:"):
        raise Exception("spotify exception")
    parsed_url = url.replace("https://open.spotify.com/", "")
    item_type = parsed_url.split("/")[0]
    item_id = parsed_url.split("/")[1]
    return item_type, item_id


def get_item_name(sp: Spotify, item_type, item_id):
    """
    Fetch the name of the item.
    :param sp: Spotify Client
    :param item_type: Type of the item
    :param item_id: id of the item
    :return String indicating the name of the item
    """
    if item_type == 'playlist':
        name = sp.playlist(playlist_id=item_id, fields='name').get('name')
    elif item_type == 'album':
        name = sp.album(album_id=item_id).get('name')
    elif item_type == 'track':
        name = sp.track(track_id=item_id).get('name')
    return sanitize(name)


def get_item_name(sp: Spotify, item_type, item_id):
    """
    Fetch the name of the item.
    :param sp: Spotify Client
    :param item_type: Type of the item
    :param item_id: id of the item
    :return String indicating the name of the item
    """
    if item_type == 'playlist':
        name = sp.playlist(playlist_id=item_id, fields='name').get('name')
    elif item_type == 'album':
        name = sp.album(album_id=item_id).get('name')
    elif item_type == 'track':
        name = sp.track(track_id=item_id).get('name')
    return sanitize(name)


def get_item_data(sp: Spotify, item_type, item_id):
    """
    Fetch the name of the item.
    :param sp: Spotify Client
    :param item_type: Type of the item
    :param item_id: id of the item
    :return String indicating the name of the item
    """
    if item_type == 'playlist':
        name = sp.playlist(playlist_id=item_id)
    elif item_type == 'album':
        name = sp.album(album_id=item_id)
    elif item_type == 'track':
        name = sp.track(track_id=item_id)
    return name


def validate_spotify_url(url):
    """
    Validate the URL and determine if the item type is supported.
    :return Boolean indicating whether or not item is supported
    """
    item_type, item_id = parse_spotify_url(url)
    if item_type not in ['album', 'track', 'playlist']:
        return False
    if item_id is None:
        return False
    return True


def parse_data(data, item_type):
    if item_type == 'playlist':
        mutated_data = {'name': data.get("name"), 'webpage_url': data.get(
            "external_urls").get("spotify"), 'tracks': [parse_track(track.get('track')) for track in data.get("tracks").get('items')]}
    elif item_type == 'track':
        mutated_data = parse_track(data)
    elif item_type == 'album':
        mutated_data = {'name': data.get("name"), 'webpage_url': data.get(
            "external_urls").get("spotify"), 'tracks': [parse_track(track) for track in data.get('tracks').get('items')]}
    return mutated_data


def parse_track(data):
    return {'name': data.get('name'), 'artists': [artist.get('name') for artist in data.get('artists')], 'webpage_url': data.get('external_urls').get('spotify'), 'duration':int(data.get('duration_ms')/1000)}


def create_query_from_track(data: dict):
    artists = ""
    for artist in data.get('artists'):
        artists += (artist+" ")
    return f"{data.get('name')} by {artists}"
