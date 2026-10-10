# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)

from __future__ import absolute_import, division, unicode_literals
import time
from traceback import format_exc
from xbmc import Monitor
from api import Api
from nexttrack import clear_properties
from playbackmanager import POPUP_ABORTED, PlaybackManager
from player import get_player
from statichelper import to_unicode
from utils import decode_json, get_property, get_setting_bool, kodi_version_major, log as ulog


# Nothing queued after this track yet: SpotifyKodiConnect appends later
# playlist pages and autoplay suggestions in the background, so look again.
NO_NEXT_RETRY_SECS = 3


class NextTrackMonitor(Monitor):
    """Service monitor for Next Track."""

    _retry_at = 0.0

    def __init__(self):
        self.player = get_player()
        self.api = Api()
        self.playback_manager = PlaybackManager()
        Monitor.__init__(self)

    def log(self, msg, level=1):
        ulog(msg, name=self.__class__.__name__, level=level)

    def run(self):
        """Main service loop."""
        self.log('Service started', 0)

        while not self.abortRequested():
            if self.waitForAbort(1):
                break

            try:
                self._check_playback()
            except Exception:  # pylint: disable=broad-except
                # Never let an unexpected error kill the service: log it,
                # stop tracking the current playback and keep monitoring.
                self.log('Unexpected error in service loop:\n%s' % format_exc(), 0)
                self._reset_after_error()

        self.log('Service stopped', 0)

    def _reset_after_error(self):
        """Best-effort cleanup after an unexpected error in the service loop."""
        for cleanup in (self.player.disable_tracking,
                        clear_properties,
                        self.player.reset_queue,
                        self.api.reset_addon_data):
            try:
                cleanup()
            except Exception:  # pylint: disable=broad-except
                self.log('Cleanup after error failed:\n%s' % format_exc(), 0)

    def _check_playback(self):  # pylint: disable=too-many-branches,too-many-return-statements
        """Check the current playback and launch Next Track when due."""
        if not self.player.is_tracking():
            return

        if bool(get_property('PseudoTVRunning') == 'True'):
            self.player.disable_tracking()
            return

        if kodi_version_major() >= 18 and self.player.isExternalPlayer():
            self.log('Next Track tracking stopped, external player detected', 2)
            self.player.disable_tracking()
            return

        last_file = self.player.get_last_file()
        try:
            current_file = to_unicode(self.player.getPlayingFile())
        except RuntimeError:
            self.log('Next Track tracking stopped, failed player.getPlayingFile()', 2)
            self.player.disable_tracking()
            return

        if (current_file.startswith((
                'bluray://', 'dvd://', 'udf://', 'iso9660://', 'cdda://'))
                or current_file.endswith((
                    '.bdmv', '.iso', '.ifo'))):
            self.log('Next Track tracking stopped, Blu-ray/DVD/CD playing', 2)
            self.player.disable_tracking()
            return

        if last_file and last_file == current_file:
            return

        try:
            total_time = self.player.getTotalTime()
        except RuntimeError:
            self.log('Next Track tracking stopped, failed player.getTotalTime()', 2)
            self.player.disable_tracking()
            return

        if total_time == 0:
            self.log('Next Track tracking stopped, no file is playing', 2)
            self.player.disable_tracking()
            return

        try:
            play_time = self.player.getTime()
        except RuntimeError:
            self.log('Next Track tracking stopped, failed player.getTime()', 2)
            self.player.disable_tracking()
            return

        notification_time = self.api.notification_time(total_time=total_time)
        if total_time - play_time > notification_time:
            return
        if time.monotonic() < self._retry_at:
            return

        self.player.set_last_file(current_file)
        self.log('Show notification as track (length %d secs) ends in %d secs' % (total_time, notification_time), 2)
        result = self.playback_manager.launch_next_track()
        if result == POPUP_ABORTED:
            # Popup closed because the user sought back out of the trigger
            # zone: forget this file so the overlay re-arms for it.
            self.player.set_last_file(None)
            return
        if result is None:
            self.player.set_last_file(None)
            self._retry_at = time.monotonic() + NO_NEXT_RETRY_SECS
            return
        self.log('Next Track autoplay succeeded', 2)
        # With crossfade the next track starts (and re-enables tracking in
        # onAVStarted) before the countdown ends: leave that track tracked.
        if self._is_playing_file(current_file):
            self.player.disable_tracking()

    def _is_playing_file(self, filename):
        try:
            return to_unicode(self.player.getPlayingFile()) == filename
        except RuntimeError:
            return False

    def onNotification(self, sender, method, data):  # pylint: disable=invalid-name
        """Notification event handler for accepting data from add-ons."""
        if not method.endswith('nexttrack_data'):
            return

        decoded_data, encoding = decode_json(data)
        if decoded_data is None:
            self.log('Received data from sender %s is not JSON: %s' % (sender, data), 2)
            return

        decoded_data.update(id='%s_play_action' % sender.replace('.SIGNAL', ''))
        self.api.addon_data_received(decoded_data, encoding=encoding)
        self.player.enable_tracking()
        self.player.reset_queue()
