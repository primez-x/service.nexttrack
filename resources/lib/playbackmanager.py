# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)

from __future__ import absolute_import, division, unicode_literals
from xbmc import sleep
from api import Api
from player import get_player
from playitem import PlayItem
from state import State
from nexttrack import NextTrack
from utils import calculate_progress_steps, event, log as ulog

# Outcomes of a Next Track popup (see PlaybackManager.launch_popup)
POPUP_PLAYED = 'played'    # countdown finished and the next item was started
POPUP_DONE = 'done'        # countdown finished (or nothing to do); Kodi advances itself
POPUP_ABORTED = 'aborted'  # user sought out of the trigger zone; re-arm for this track
POPUP_CLOSED = 'closed'    # playback moved on (file, playlist position or track changed)
POPUP_STOPPED = 'stopped'  # player was not running when the popup started


class PlaybackManager:
    _shared_state = {}

    def __init__(self):
        self.__dict__ = self._shared_state
        self.api = Api()
        self.play_item = PlayItem()
        self.state = State()
        self.player = get_player()

    def log(self, msg, level=2):
        ulog(msg, name=self.__class__.__name__, level=level)

    def launch_next_track(self):
        """Run the Next Track popup for the current track and return its result."""
        track, source = self.play_item.get_next()
        if not track:
            self.log('Error: no track could be found to play next...exiting', 1)
            return None
        self.log('track details %s' % track, 2)
        result = self.launch_popup(track, source)
        play_next = result == POPUP_PLAYED
        self.state.playing_next = play_next

        if result == POPUP_ABORTED:
            # User sought back out of the trigger zone: keep the queued item and
            # add-on data so the popup can re-arm later in the same track.
            self.log('popup aborted, re-arming for the current track', 2)
            return result

        if source != 'playlist' and not play_next and self.state.queued:
            self.state.queued = self.api.dequeue_next_item()
        if result == POPUP_STOPPED:
            self.log('Stopping playback', 2)
            self.player.stop()

        self.api.reset_addon_data()
        return result

    def launch_popup(self, track, source=None):
        """Show the popup and act on its outcome; returns a POPUP_* result."""
        track_id = track.get('trackid')
        if self.state.current_track_id == track_id:
            return POPUP_DONE

        if source != 'playlist' and not self.state.queued:
            self.state.queued = self.api.queue_next_item(track)

        next_track_widget = NextTrack()
        try:
            next_track_widget.set_source(source)
            result = self.show_popup_and_wait(track, next_track_widget, source)
        finally:
            # Always clear the overlay, even if the countdown raised.
            next_track_widget.close()

        if result != POPUP_DONE:
            return result

        if not self.state.track:
            self.log('exit launch_popup early due to disabled tracking', 2)
            return POPUP_DONE

        if source == 'playlist':
            self.log('playlist source: overlay only, letting Kodi auto-advance', 2)
            return POPUP_DONE

        self.log('playing next track', 2)
        if self.state.current_track_id is not None:
            event(message='NEXTTRACKPLAYEDSIGNAL', data={'trackid': self.state.current_track_id}, encoding='base64')

        if self.api.has_addon_data():
            self.api.play_addon_item()
        elif self.state.queued:
            self.player.playnext()

        return POPUP_PLAYED

    def show_popup_and_wait(self, track, next_track_widget, source=None):
        """Show non-blocking overlay until track ends or time runs out.

        Returns POPUP_DONE when the countdown ran out, POPUP_ABORTED when the
        user sought out of the trigger zone, POPUP_CLOSED when playback moved
        on, and POPUP_STOPPED when the player was no longer running.
        The caller is responsible for closing the widget.
        """
        UPDATE_INTERVAL_MS = 100
        try:
            play_time = self.player.getTime()
            total_time = self.player.getTotalTime()
        except RuntimeError:
            self.log('exit early because player is no longer running', 2)
            return POPUP_STOPPED

        playback_snapshot = self._playback_snapshot(source)
        if playback_snapshot is None:
            return POPUP_STOPPED

        period_sec = total_time - play_time
        progress_step_size = calculate_progress_steps(
            period_sec, update_interval_sec=UPDATE_INTERVAL_MS / 1000.0
        )
        next_track_widget.set_item(track)
        next_track_widget.set_progress_step_size(progress_step_size)
        next_track_widget.show()

        initial_total_time = total_time
        notification_threshold = self.api.notification_time(total_time=total_time)

        while self.player.isPlaying() and (total_time - play_time > 1):
            try:
                play_time = self.player.getTime()
                total_time = self.player.getTotalTime()
            except RuntimeError:
                return POPUP_CLOSED

            if self._playback_snapshot_changed(playback_snapshot, source):
                return POPUP_CLOSED

            remaining = total_time - play_time
            # User rewound out of the notification zone: hide overlay so we don't show "130 sec until next track"
            if remaining > notification_threshold:
                self.log('closing overlay because playback left the notification zone', 2)
                return POPUP_ABORTED
            if abs(total_time - initial_total_time) > initial_total_time * 0.1:
                self.log('closing overlay because track duration changed', 2)
                return POPUP_ABORTED
            runtime = track.get('runtime') or track.get('duration')
            if not self.state.pause:
                next_track_widget.update_progress_control(remaining=remaining, runtime=runtime)
            sleep(UPDATE_INTERVAL_MS)

        return POPUP_DONE

    def _playback_snapshot(self, source):
        try:
            player_file = self.player.getPlayingFile()
        except RuntimeError:
            self.log('exit early because player file is no longer available', 2)
            return None

        playlist_position = None
        if source == 'playlist':
            playlist_position = self.play_item.get_playlist_position()

        return {
            'file': player_file,
            'playlist_position': playlist_position,
            'current_track_id': self.state.current_track_id,
        }

    def _playback_snapshot_changed(self, snapshot, source):
        try:
            player_file = self.player.getPlayingFile()
        except RuntimeError:
            self.log('closing overlay because player file is no longer available', 2)
            return True

        if player_file != snapshot.get('file'):
            self.log('closing overlay because player file changed', 2)
            return True

        if source == 'playlist':
            playlist_position = self.play_item.get_playlist_position()
            if playlist_position != snapshot.get('playlist_position'):
                self.log('closing overlay because playlist position changed', 2)
                return True

        if self.state.current_track_id != snapshot.get('current_track_id'):
            self.log('closing overlay because active track changed', 2)
            return True

        return False
