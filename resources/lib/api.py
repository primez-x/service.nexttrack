# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)

from __future__ import absolute_import, division, unicode_literals
from xbmc import sleep, PLAYLIST_VIDEO, PLAYLIST_MUSIC
from utils import event, get_int, get_property, get_setting_bool, get_setting_int, jsonrpc, log as ulog


class Api:
    """API class for Next Track playlist and player operations."""
    _shared_state = {}
    _playerid_cache = None
    _playlistid_cache = None
    # Playlist ID and identity of the confirmed add-on-owned entry.
    queued_item = None

    PLAYER_PLAYLIST = {
        'video': PLAYLIST_VIDEO,  # 1
        'audio': PLAYLIST_MUSIC   # 0
    }

    def __init__(self):
        self.__dict__ = self._shared_state
        self.data = {}
        self.encoding = 'base64'

    def log(self, msg, level=2, *args):  # pylint: disable=keyword-arg-before-vararg
        ulog(msg, *args, name=self.__class__.__name__, level=level)

    def has_addon_data(self):
        return self.data

    def reset_addon_data(self):
        self.data = {}

    @staticmethod
    def clear_caches():
        """Invalidate player/playlist ID caches (call when playback stops/ends/errors)."""
        Api._playerid_cache = None
        Api._playlistid_cache = None

    def addon_data_received(self, data, encoding='base64'):
        self.log('addon_data_received called', 2)
        self.data = data
        self.encoding = encoding

    @staticmethod
    def _get_playerid():
        if Api._playerid_cache is not None:
            return Api._playerid_cache

        result = jsonrpc(method='Player.GetActivePlayers')
        result = [
            player for player in result.get('result', [{}])
            if player.get('type', 'audio') in Api.PLAYER_PLAYLIST
        ]

        playerid = get_int(result[0], 'playerid') if result else -1

        if playerid == -1:
            return None

        Api._playerid_cache = playerid
        return playerid

    @staticmethod
    def get_playlistid():
        if Api._playlistid_cache is not None:
            return Api._playlistid_cache

        playerid = Api._get_playerid()
        if playerid is None:
            return Api.PLAYER_PLAYLIST['audio']

        result = jsonrpc(
            method='Player.GetProperties',
            params={
                'playerid': playerid,
                'properties': ['playlistid'],
            }
        )
        playlistid = get_int(
            result.get('result', {}), 'playlistid', Api.PLAYER_PLAYLIST['audio']
        )
        Api._playlistid_cache = playlistid
        return playlistid

    @staticmethod
    def _queue_playlist_items(playlistid):
        """Read a complete playlist snapshot, or None when the RPC fails."""
        try:
            response = jsonrpc(method='Playlist.GetItems', params={
                'playlistid': playlistid,
                'properties': ['file'],
            })
        except (RuntimeError, TypeError, ValueError):
            return None
        if not isinstance(response, dict) or 'error' in response:
            return None
        result = response.get('result')
        if not isinstance(result, dict):
            return None
        items = result.get('items', [])
        limits = result.get('limits')
        if (not isinstance(items, list) or not isinstance(limits, dict)
                or not all(isinstance(item, dict) for item in items)
                or limits.get('start') != 0 or limits.get('end') != len(items)
                or limits.get('total') != len(items)):
            return None
        return items

    @staticmethod
    def _queue_item_positions(items, identity):
        """Find entries with the requested file or library type and ID."""
        if items is None:
            return []
        kind, value = identity
        return [
            position for position, item in enumerate(items)
            if (item.get('file') == value if kind == 'file'
                else item.get('type') == kind and item.get('id') == value)
        ]

    def queue_next_item(self, track):
        self.queued_item = None
        next_item = {}
        if not self.data:
            trackid = track.get('trackid')
            if trackid in (None, -1):
                # Without a valid song id Playlist.Add would be invalid;
                # reporting queued=True made the manager playnext() into
                # whatever happened to follow in the playlist
                self.log('Not queueing next track without a valid trackid', 1)
                return False
            identity = ('song', trackid)
            next_item.update(songid=trackid)
        elif self.data.get('play_url'):
            identity = ('file', self.data['play_url'])
            next_item.update(file=self.data['play_url'])

        if not next_item:
            return False
        playlistid = Api.get_playlistid()
        before = self._queue_playlist_items(playlistid)
        if before is None:
            return False
        try:
            result = jsonrpc(
                method='Playlist.Add',
                id=0,
                params={
                    'playlistid': playlistid,
                    'item': next_item,
                }
            )
        except (RuntimeError, TypeError, ValueError):
            return False
        if not isinstance(result, dict) or 'error' in result or result.get('result') != 'OK':
            return False
        after = self._queue_playlist_items(playlistid)
        # A pre-existing duplicate remains ambiguous even after another copy disappears.
        if (not self._queue_item_positions(before, identity)
                and len(self._queue_item_positions(after, identity)) == 1):
            self.queued_item = (playlistid, identity)
        return True

    def dequeue_next_item(self):
        """Remove only the uniquely identified entry from the original playlist."""
        queued_item, self.queued_item = self.queued_item, None
        if queued_item is None:
            return False
        playlistid, identity = queued_item
        items = self._queue_playlist_items(playlistid)
        positions = self._queue_item_positions(items, identity)
        if len(positions) != 1:
            return False
        try:
            jsonrpc(
                method='Playlist.Remove',
                id=0,
                params={
                    'playlistid': playlistid,
                    'position': positions[0],
                }
            )
        except (RuntimeError, TypeError, ValueError):
            pass
        return False

    @staticmethod
    def reset_queue():
        jsonrpc(
            method='Playlist.Remove',
            id=0,
            params={
                'playlistid': Api.get_playlistid(),
                'position': 0
            }
        )

    def get_next_in_playlist(self, position):
        result = jsonrpc(method='Playlist.GetItems', params={
            'playlistid': Api.get_playlistid(),
            'limits': {'start': position, 'end': position + 1},
            'properties': ['art', 'dateadded', 'file', 'lastplayed',
                           'playcount', 'rating', 'runtime', 'title',
                           'artist', 'album', 'track', 'year', 'duration'],
        })

        item = result.get('result', {}).get('items')

        if not item:
            self.log('Error: no next item found in playlist', 1)
            return None
        item = item[0]

        if not item.get('title'):
            item['title'] = item.get('label', '')

        self._merge_spotify_hook_properties(item)
        self._normalise_art(item)

        item['trackid'] = get_int(item, 'id')

        self.log('Found next item in playlist', 2)
        return item

    @staticmethod
    def _merge_spotify_hook_properties(item):
        """Use SpotifyKodiConnect's skin hook properties when JSON-RPC is sparse."""
        item_file = item.get('file') or ''
        spotify_file = get_property('Spotify.NextTrackFile')
        if spotify_file and item_file and spotify_file != item_file:
            return

        if not item.get('title') and get_property('Spotify.NextTrackTitle'):
            item['title'] = get_property('Spotify.NextTrackTitle')
        if not item.get('label') and get_property('Spotify.NextTrackTitle'):
            item['label'] = get_property('Spotify.NextTrackTitle')
        if not item.get('artist') and get_property('Spotify.NextTrackArtist'):
            item['artist'] = get_property('Spotify.NextTrackArtist')
        if not item.get('album') and get_property('Spotify.NextTrackAlbum'):
            item['album'] = get_property('Spotify.NextTrackAlbum')
        if not item.get('duration') and get_property('Spotify.NextTrackDuration'):
            item['duration'] = get_int(get_property('Spotify.NextTrackDuration'), default=0)

        art = item.get('art') or {}
        if not isinstance(art, dict):
            art = {}
        hook_art = {
            'thumb': get_property('Spotify.NextTrackThumb'),
            'poster': get_property('Spotify.NextTrackThumb'),
            'icon': get_property('Spotify.NextTrackThumb'),
            'fanart': get_property('Spotify.NextTrackFanart'),
            'landscape': get_property('Spotify.NextTrackFanart') or get_property('Spotify.NextTrackThumb'),
        }
        for key, value in hook_art.items():
            if value and not art.get(key):
                art[key] = value
        item['art'] = art

    @staticmethod
    def _normalise_art(item):
        art = item.get('art') or {}
        if not isinstance(art, dict):
            art = {}
        fallback = ''
        for key in ('thumb', 'poster', 'icon', 'fanart', 'landscape'):
            if art.get(key):
                fallback = art.get(key)
                break
        if fallback:
            for key in ('thumb', 'poster', 'icon', 'fanart', 'landscape'):
                if not art.get(key):
                    art[key] = fallback
        item['art'] = art

    def play_addon_item(self):
        if self.data.get('play_url'):
            self.log('Playing the next item directly', 2)
            jsonrpc(method='Player.Open', params={'item': {'file': self.data.get('play_url')}})
        else:
            self.log('Sending %s data to add-on to play', 2, self.encoding)
            event(message=self.data.get('id'), data=self.data.get('play_info'), sender='nexttrackprovider', encoding=self.encoding)

    def handle_addon_lookup_of_next_track(self):
        if not self.data:
            return None
        self.log('Returning next track data', 2)
        return self.data.get('next_track')

    def handle_addon_lookup_of_current_track(self):
        if not self.data:
            return None
        self.log('Returning current track data', 2)
        return self.data.get('current_track')

    def _provider_int(self, key):
        value = self.data.get(key)
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            self.log('Ignoring invalid %s from provider', 1, key)
            return None

    def notification_time(self, total_time=None):
        notification_time = self._provider_int('notification_time')
        if notification_time is not None:
            return max(0, notification_time)

        notification_offset = self._provider_int('notification_offset')
        if total_time and notification_offset is not None:
            return total_time - notification_offset

        return get_setting_int('notificationSeconds', 15)
