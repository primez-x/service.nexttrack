# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)

from __future__ import absolute_import, division, unicode_literals
from xbmc import sleep, PLAYLIST_VIDEO, PLAYLIST_MUSIC
from utils import event, get_int, get_setting_bool, get_setting_int, jsonrpc, log as ulog


class Api:
    """API class for Next Track playlist and player operations."""
    _shared_state = {}
    _playerid_cache = None
    _playlistid_cache = None

    PLAYER_PLAYLIST = {
        'video': PLAYLIST_VIDEO,  # 1
        'audio': PLAYLIST_MUSIC   # 0
    }

    def __init__(self):
        self.__dict__ = self._shared_state
        self.data = {}
        self.encoding = 'base64'

    def log(self, msg, level=2):
        ulog(msg, name=self.__class__.__name__, level=level)

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
        self.log('addon_data_received called with data %s' % data, 2)
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

    def queue_next_item(self, track):
        next_item = {}
        if not self.data:
            next_item.update(songid=track.get('trackid'))
        elif self.data.get('play_url'):
            next_item.update(file=self.data.get('play_url'))

        if next_item:
            jsonrpc(
                method='Playlist.Add',
                id=0,
                params={
                    'playlistid': Api.get_playlistid(),
                    'item': next_item
                }
            )

        return bool(next_item)

    @staticmethod
    def dequeue_next_item():
        jsonrpc(
            method='Playlist.Remove',
            id=0,
            params={
                'playlistid': Api.get_playlistid(),
                'position': 1
            }
        )
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

        item['trackid'] = get_int(item, 'id')

        self.log('Next item in playlist: %s' % item, 2)
        return item

    def play_addon_item(self):
        if self.data.get('play_url'):
            self.log('Playing the next item directly: %(play_url)s' % self.data, 2)
            jsonrpc(method='Player.Open', params={'item': {'file': self.data.get('play_url')}})
        else:
            self.log('Sending %(encoding)s data to add-on to play: %(play_info)s' % dict(encoding=self.encoding, **self.data), 2)  # pylint: disable=use-dict-literal
            event(message=self.data.get('id'), data=self.data.get('play_info'), sender='nexttrackprovider', encoding=self.encoding)

    def handle_addon_lookup_of_next_track(self):
        if not self.data:
            return None
        self.log('handle_addon_lookup_of_next_track returning data %(next_track)s' % self.data, 2)
        return self.data.get('next_track')

    def handle_addon_lookup_of_current_track(self):
        if not self.data:
            return None
        self.log('handle_addon_lookup_of_current_track returning data %(current_track)s' % self.data, 2)
        return self.data.get('current_track')

    def notification_time(self, total_time=None):
        if self.data.get('notification_time'):
            return int(self.data.get('notification_time'))

        if total_time and self.data.get('notification_offset'):
            return total_time - int(self.data.get('notification_offset'))

        return get_setting_int('notificationSeconds', 15)
