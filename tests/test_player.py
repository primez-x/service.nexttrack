from __future__ import absolute_import, division, unicode_literals

import importlib
import sys
import unittest
from unittest.mock import patch

from test_playbackmanager import (
    KODI_MODULES, LIB_DIR, MISSING, RUNTIME_MODULES, install_kodi_mocks,
)


class PlayerTests(unittest.TestCase):
    def setUp(self):
        self.modules = KODI_MODULES + RUNTIME_MODULES
        self.originals = {name: sys.modules.get(name, MISSING) for name in self.modules}
        for name in self.modules:
            sys.modules.pop(name, None)
        self.original_path = list(sys.path)
        sys.path.insert(0, str(LIB_DIR))
        install_kodi_mocks()
        self.module = importlib.import_module('player')
        self.player = self.module.NextTrackPlayer()
        self.player.isPlayingAudio = lambda: True
        self.state = self.player.state

    def tearDown(self):
        for name, original in self.originals.items():
            if original is MISSING:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original
        sys.path[:] = self.original_path

    def test_new_audio_file_clears_stale_pause_and_handoff(self):
        self.state.pause = True
        self.state.playing_next = True
        self.player.onPlayBackStarted()
        self.assertFalse(self.state.pause)
        self.assertFalse(self.state.playing_next)
        self.assertTrue(self.state.track)

    def test_video_does_not_enable_audio_tracking(self):
        self.player.isPlayingAudio = lambda: False
        self.player.onPlayBackStarted()
        self.assertFalse(self.state.track)

    def test_handoff_keeps_provider_data_until_new_file_starts(self):
        self.state.playing_next = True
        self.player.api.data = {'next_track': {'trackid': 2}}
        self.player.onPlayBackEnded()
        self.assertTrue(self.state.playing_next)
        self.assertTrue(self.player.api.has_addon_data())

    def test_final_track_end_clears_later_provider_data_and_caches(self):
        self.state.playing_next = True
        self.player.onPlayBackStarted()
        self.player.api.data = {'next_track': None}
        self.module.Api._playerid_cache = 0
        self.module.Api._playlistid_cache = 0
        self.player.onPlayBackEnded()
        self.assertFalse(self.state.track)
        self.assertFalse(self.state.playing_next)
        self.assertFalse(self.player.api.has_addon_data())
        self.assertIsNone(self.module.Api._playerid_cache)
        self.assertIsNone(self.module.Api._playlistid_cache)

    def test_stop_and_error_reset_queue_data_and_state(self):
        for callback in (self.player.onPlayBackStopped, self.player.onPlayBackError):
            with self.subTest(callback=callback.__name__):
                self.state.track = self.state.pause = self.state.queued = True
                self.state.playing_next = True
                self.player.api.data = {'next_track': {'trackid': 2}}
                with patch.object(self.player.api, 'reset_queue') as reset_queue:
                    callback()
                reset_queue.assert_called_once_with()
                self.assertFalse(self.state.track)
                self.assertFalse(self.state.pause)
                self.assertFalse(self.state.queued)
                self.assertFalse(self.state.playing_next)
                self.assertFalse(self.player.api.has_addon_data())

    def test_incidental_state_and_service_construction_preserve_live_state(self):
        self.state.track = True
        self.state.playing_next = True
        self.state.current_track_id = 42
        self.state.last_file = 'current.mp3'
        other = self.module.State()
        self.assertTrue(other.track)
        self.assertTrue(other.playing_next)
        self.assertEqual(other.current_track_id, 42)
        self.assertEqual(other.last_file, 'current.mp3')
        importlib.import_module('playbackmanager').PlaybackManager()
        self.assertTrue(self.state.track)
        self.assertEqual(self.state.current_track_id, 42)

    def test_explicit_reset_clears_shared_state_for_all_consumers(self):
        other = self.module.State()
        self.state.track = self.state.pause = self.state.queued = True
        self.state.current_track_id = 42
        self.state.reset()
        self.assertFalse(other.track)
        self.assertFalse(other.pause)
        self.assertFalse(other.queued)
        self.assertIsNone(other.current_track_id)

    def test_wrappers_preserve_lazy_log_arguments(self):
        class Unformattable:
            def __str__(self):
                raise AssertionError('suppressed log was formatted')

        utils = importlib.import_module('utils')
        wrappers = (
            self.module.Api(),
            importlib.import_module('playitem').PlayItem(),
            importlib.import_module('playbackmanager').PlaybackManager(),
            importlib.import_module('monitor').NextTrackMonitor(),
        )
        with patch.object(utils, 'get_setting_int', return_value=0), \
                patch.object(utils, 'get_global_setting', return_value=False):
            utils.clear_setting_cache()
            for wrapper in wrappers:
                with self.subTest(wrapper=wrapper.__class__.__name__):
                    wrapper.log('suppressed %s', 2, Unformattable())
