# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)

from __future__ import absolute_import, division, unicode_literals
from xbmc import PlayList
from api import Api
from player import NextTrackPlayer
from state import State
from utils import log as ulog


class PlayItem:
    _shared_state = {}

    def __init__(self):
        self.__dict__ = self._shared_state
        self.api = Api()
        self.player = NextTrackPlayer()
        self.state = State()

    def log(self, msg, level=2):
        ulog(msg, name=self.__class__.__name__, level=level)

    def get_playlist_position(self):
        playlist = PlayList(self.api.get_playlistid())
        position = playlist.getposition()
        if playlist.size() > 1 and position < (playlist.size() - 1):
            return position + 1
        return False

    def get_next(self):
        """Get next track to play, based on current music source."""
        track = None
        source = None
        position = self.get_playlist_position()
        has_addon_data = self.api.has_addon_data()

        if has_addon_data:
            track = self.api.handle_addon_lookup_of_next_track()
            current_track = self.api.handle_addon_lookup_of_current_track()
            if current_track:
                self.state.current_track_id = current_track.get('trackid')
            source = 'addon' if not position else 'playlist'

        elif position:
            track = self.api.get_next_in_playlist(position)
            source = 'playlist'

        return track, source
