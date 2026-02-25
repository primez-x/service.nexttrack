# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)

from __future__ import absolute_import, division, unicode_literals
from utils import get_setting_bool


class State:
    _shared_state = {}

    def __init__(self):
        self.__dict__ = self._shared_state
        self.include_played = get_setting_bool('includePlayed')
        self.current_track_id = None
        self.last_file = None
        self.track = False
        self.pause = False
        self.queued = False
        self.playing_next = False
