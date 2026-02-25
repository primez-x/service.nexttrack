# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)

from __future__ import absolute_import, division, unicode_literals
from xbmc import sleep
from api import Api
from demo import DemoOverlay
from player import NextTrackPlayer
from playitem import PlayItem
from state import State
from nexttrack import NextTrack
from utils import addon_path, calculate_progress_steps, clear_property, event, get_setting_bool, get_setting_int, log as ulog, set_property


class PlaybackManager:
    _shared_state = {}

    def __init__(self):
        self.__dict__ = self._shared_state
        self.api = Api()
        self.play_item = PlayItem()
        self.state = State()
        self.player = NextTrackPlayer()
        self.demo = DemoOverlay(12005)

    def log(self, msg, level=2):
        ulog(msg, name=self.__class__.__name__, level=level)

    def handle_demo(self):
        if get_setting_bool('enableDemoMode'):
            self.log('Next Track DEMO mode enabled, skipping automatically to the end', 0)
            self.demo.show()
            try:
                total_time = self.player.getTotalTime()
                self.player.seekTime(total_time - 15)
            except RuntimeError as exc:
                self.log('Failed to seekTime(): %s' % exc, 0)
        else:
            self.demo.hide()

    def launch_next_track(self):
        enable_playlist = get_setting_bool('enablePlaylist')
        track, source = self.play_item.get_next()
        self.log('Playlist setting: %s' % enable_playlist)
        if source == 'playlist' and not enable_playlist:
            self.log('Playlist integration disabled', 2)
            return
        if not track:
            self.log('Error: no track could be found to play next...exiting', 1)
            return
        self.log('track details %s' % track, 2)
        play_next, keep_playing = self.launch_popup(track, source)
        self.state.playing_next = play_next

        if not play_next and self.state.queued:
            self.state.queued = self.api.dequeue_next_item()
        if not keep_playing:
            self.log('Stopping playback', 2)
            self.player.stop()

        self.api.reset_addon_data()

    def launch_popup(self, track, source=None):
        track_id = track.get('trackid')
        no_play_count = track.get('playcount') is None or track.get('playcount') == 0
        include_play_count = True if self.state.include_played else no_play_count
        if not include_play_count or self.state.current_track_id == track_id:
            return False, True

        if source != 'playlist':
            self.state.queued = self.api.queue_next_item(track)

        if get_setting_int('simpleMode') == 0:
            next_track_page = NextTrack('script-nexttrack-nexttrack-simple.xml', addon_path(), 'default', '1080i')
        else:
            next_track_page = NextTrack('script-nexttrack-nexttrack.xml', addon_path(), 'default', '1080i')

        showing = self.show_popup_and_wait(track, next_track_page)
        next_track_page.close()
        clear_property('service.nexttrack.dialog')

        if not self.state.track:
            self.log('exit launch_popup early due to disabled tracking', 2)
            return False, showing

        self.log('playing next track', 2)
        if self.state.current_track_id is not None:
            event(message='NEXTTRACKPLAYEDSIGNAL', data={'trackid': self.state.current_track_id}, encoding='base64')

        if source == 'playlist':
            self.log('playlist source: letting Kodi auto-advance', 2)
        elif self.api.has_addon_data():
            self.api.play_addon_item()
        elif self.state.queued:
            self.player.playnext()

        return True, True

    def show_popup_and_wait(self, track, next_track_page):
        """Show informational overlay until track ends or time runs out."""
        try:
            play_time = self.player.getTime()
            total_time = self.player.getTotalTime()
        except RuntimeError:
            self.log('exit early because player is no longer running', 2)
            return False
        progress_step_size = calculate_progress_steps(total_time - play_time)
        next_track_page.set_item(track)
        next_track_page.set_progress_step_size(progress_step_size)
        next_track_page.show()
        set_property('service.nexttrack.dialog', 'true')

        while self.player.isPlaying() and (total_time - play_time > 1):
            try:
                play_time = self.player.getTime()
                total_time = self.player.getTotalTime()
            except RuntimeError:
                next_track_page.close()
                return True

            remaining = total_time - play_time
            runtime = track.get('runtime') or track.get('duration')
            if not self.state.pause:
                next_track_page.update_progress_control(remaining=remaining, runtime=runtime)
            sleep(100)

        return True
