from __future__ import absolute_import, division, unicode_literals

import importlib
import json
import sys
import types
import unittest
from pathlib import Path


LIB_DIR = Path(__file__).resolve().parents[1] / "resources" / "lib"
RUNTIME_MODULES = (
    "api",
    "nexttrack",
    "playbackmanager",
    "player",
    "playitem",
    "state",
    "statichelper",
    "utils",
)
KODI_MODULES = ("xbmc", "xbmcaddon", "xbmcgui", "xbmcvfs")
MISSING = object()


def install_kodi_mocks():
    xbmc = types.ModuleType("xbmc")
    xbmc.LOGDEBUG = 0
    xbmc.LOGINFO = 1
    xbmc.PLAYLIST_MUSIC = 0
    xbmc.PLAYLIST_VIDEO = 1
    xbmc.sleep = lambda _milliseconds: None
    xbmc.log = lambda *_args, **_kwargs: None
    xbmc.executebuiltin = lambda *_args, **_kwargs: None
    xbmc.getCondVisibility = lambda _condition: False
    xbmc.getInfoLabel = lambda label: "20.0" if label == "System.BuildVersion" else ""
    xbmc.getRegion = lambda _key: "%H:%M"
    xbmc.executeJSONRPC = lambda _payload: json.dumps({"result": {}})

    class MockPlayer(object):
        def __init__(self, *args, **kwargs):
            pass

    class MockMonitor(object):
        def __init__(self, *args, **kwargs):
            pass

        def waitForAbort(self, _timeout):
            return False

    class MockPlayList(object):
        def __init__(self, _playlist_id):
            pass

        def getposition(self):
            return 0

        def size(self):
            return 0

    xbmc.Player = MockPlayer
    xbmc.Monitor = MockMonitor
    xbmc.PlayList = MockPlayList

    xbmcaddon = types.ModuleType("xbmcaddon")

    class MockAddon(object):
        def getAddonInfo(self, key):
            values = {
                "id": "service.nexttrack",
                "path": str(LIB_DIR.parents[1]),
            }
            return values.get(key, "")

        def getSetting(self, _key):
            return ""

        def getSettingBool(self, _key):
            return False

        def getSettingInt(self, key):
            if key == "notificationSeconds":
                return 15
            return 2

        def getLocalizedString(self, string_id):
            return str(string_id)

    xbmcaddon.Addon = MockAddon

    xbmcgui = types.ModuleType("xbmcgui")
    xbmcgui.ACTION_NAV_BACK = 92
    xbmcgui.ACTION_PREVIOUS_MENU = 10
    xbmcgui.getCurrentWindowId = lambda: 10500
    xbmcgui.getCurrentWindowDialogId = lambda: 0

    class MockWindow(object):
        properties = {}

        def __init__(self, window_id):
            self.window_id = window_id

        def getProperty(self, key):
            return self.properties.get((self.window_id, key), "")

        def setProperty(self, key, value):
            self.properties[(self.window_id, key)] = value

        def clearProperty(self, key):
            self.properties.pop((self.window_id, key), None)

    class MockWindowXMLDialog(object):
        def show(self):
            pass

        def close(self):
            pass

        def setProperty(self, _key, _value):
            pass

    class MockDialog(object):
        def notification(self, *_args, **_kwargs):
            pass

    xbmcgui.Window = MockWindow
    xbmcgui.WindowXMLDialog = MockWindowXMLDialog
    xbmcgui.Dialog = MockDialog

    xbmcvfs = types.ModuleType("xbmcvfs")
    xbmcvfs.translatePath = lambda _path: str(LIB_DIR.parents[1])

    sys.modules["xbmc"] = xbmc
    sys.modules["xbmcaddon"] = xbmcaddon
    sys.modules["xbmcgui"] = xbmcgui
    sys.modules["xbmcvfs"] = xbmcvfs


def load_playbackmanager_subject():
    install_kodi_mocks()
    playbackmanager = importlib.import_module("playbackmanager")
    playbackmanager.PlaybackManager._shared_state = {}

    class FakeNextTrack(object):
        instances = []

        def __init__(self):
            self.source = None
            self.close_calls = 0
            self.progress_updates = []
            FakeNextTrack.instances.append(self)

        def set_source(self, source):
            self.source = source

        def set_item(self, item):
            self.item = item

        def set_progress_step_size(self, step_size):
            self.progress_step_size = step_size

        def show(self):
            self.shown = True

        def close(self):
            self.close_calls += 1

        def update_progress_control(self, **kwargs):
            self.progress_updates.append(kwargs)

    playbackmanager.NextTrack = FakeNextTrack
    playbackmanager.sleep = lambda _milliseconds: None
    playbackmanager.event = lambda **_kwargs: None
    return playbackmanager, FakeNextTrack


class FakeState(object):
    def __init__(self, current_track_id=None, queued=False):
        self.current_track_id = current_track_id
        self.last_file = None
        self.track = True
        self.pause = False
        self.queued = queued
        self.playing_next = False


class FakeApi(object):
    def __init__(self, has_addon_data=False, notification_time=15, queue_result=True):
        self._has_addon_data = has_addon_data
        self._notification_time = notification_time
        self._queue_result = queue_result
        self.queue_calls = []
        self.dequeue_calls = 0
        self.reset_calls = 0
        self.play_addon_calls = 0

    def queue_next_item(self, track):
        self.queue_calls.append(track)
        return self._queue_result

    def dequeue_next_item(self):
        self.dequeue_calls += 1
        return False

    def reset_addon_data(self):
        self.reset_calls += 1

    def has_addon_data(self):
        return self._has_addon_data

    def play_addon_item(self):
        self.play_addon_calls += 1

    def notification_time(self, total_time=None):
        return self._notification_time


class FakePlayer(object):
    def __init__(
            self, times, totals, playing, files=None, on_get_time_call=None):
        self._times = list(times)
        self._totals = list(totals)
        self._playing = list(playing)
        self._files = list(files or ["current.mp3"])
        self._on_get_time_call = on_get_time_call or {}
        self._get_time_calls = 0
        self.playnext_calls = 0
        self.stop_calls = 0

    @staticmethod
    def _next(values):
        if len(values) > 1:
            return values.pop(0)
        return values[0]

    def getTime(self):
        self._get_time_calls += 1
        callback = self._on_get_time_call.get(self._get_time_calls)
        if callback:
            callback()
        return self._next(self._times)

    def getTotalTime(self):
        return self._next(self._totals)

    def isPlaying(self):
        return self._next(self._playing)

    def getPlayingFile(self):
        return self._next(self._files)

    def playnext(self):
        self.playnext_calls += 1

    def stop(self):
        self.stop_calls += 1


class FakePlayItem(object):
    def __init__(self, track, source, positions=None):
        self.track = track
        self.source = source
        self.positions = list(positions or [False])

    def get_next(self):
        return self.track, self.source

    def get_playlist_position(self):
        if len(self.positions) > 1:
            return self.positions.pop(0)
        return self.positions[0]


def make_manager(playbackmanager, api, player, state, play_item=None):
    manager = playbackmanager.PlaybackManager()
    manager.api = api
    manager.player = player
    manager.state = state
    if play_item is not None:
        manager.play_item = play_item
    return manager


class PlaybackManagerTests(unittest.TestCase):
    def setUp(self):
        self._module_names = KODI_MODULES + RUNTIME_MODULES
        self._original_modules = {
            name: sys.modules.get(name, MISSING) for name in self._module_names
        }
        for module_name in self._module_names:
            sys.modules.pop(module_name, None)
        self._original_path = list(sys.path)
        sys.path.insert(0, str(LIB_DIR))
        self.playbackmanager, self.widgets = load_playbackmanager_subject()

    def tearDown(self):
        for module_name in self._module_names:
            original = self._original_modules[module_name]
            if original is MISSING:
                sys.modules.pop(module_name, None)
            else:
                sys.modules[module_name] = original
        sys.path[:] = self._original_path

    def test_rewind_out_of_trigger_zone_aborts_without_playnext(self):
        state = FakeState()
        api = FakeApi(has_addon_data=False, notification_time=15, queue_result=True)
        player = FakePlayer(
            times=[85, 70],
            totals=[100, 100],
            playing=[True],
            files=["library-track.mp3", "library-track.mp3"],
        )
        manager = make_manager(self.playbackmanager, api, player, state)

        play_next, keep_playing = manager.launch_popup(
            {"trackid": 2, "duration": 180}, source="library"
        )

        self.assertIs(play_next, False)
        self.assertIs(keep_playing, True)
        self.assertEqual(player.playnext_calls, 0)
        self.assertGreaterEqual(self.widgets.instances[-1].close_calls, 1)

    def test_player_file_change_during_countdown_aborts_stale_playnext(self):
        state = FakeState()
        api = FakeApi(has_addon_data=False, notification_time=15, queue_result=True)
        player = FakePlayer(
            times=[90, 99],
            totals=[100, 100],
            playing=[True, False],
            files=["track-a.mp3", "track-b.mp3"],
        )
        manager = make_manager(self.playbackmanager, api, player, state)

        play_next, keep_playing = manager.launch_popup(
            {"trackid": 3, "duration": 180}, source="library"
        )

        self.assertIs(play_next, False)
        self.assertIs(keep_playing, True)
        self.assertEqual(player.playnext_calls, 0)

    def test_active_track_change_during_countdown_aborts_provider_play_action(self):
        state = FakeState(current_track_id="current")
        api = FakeApi(has_addon_data=True, notification_time=15, queue_result=True)
        player = FakePlayer(
            times=[90, 99],
            totals=[100, 100],
            playing=[True, False],
            files=["addon-track.mp3", "addon-track.mp3"],
            on_get_time_call={
                2: lambda: setattr(state, "current_track_id", "different")
            },
        )
        manager = make_manager(self.playbackmanager, api, player, state)

        play_next, keep_playing = manager.launch_popup(
            {"trackid": "next", "duration": 180}, source="addon"
        )

        self.assertIs(play_next, False)
        self.assertIs(keep_playing, True)
        self.assertEqual(api.play_addon_calls, 0)

    def test_playlist_position_change_during_countdown_stays_passive(self):
        track = {
            "trackid": 4,
            "file": "http://127.0.0.1:52309/track/abc/180.wav",
            "duration": 180,
        }
        state = FakeState(queued=True)
        api = FakeApi(has_addon_data=True, notification_time=15, queue_result=True)
        player = FakePlayer(
            times=[90, 99],
            totals=[100, 100],
            playing=[True, False],
            files=[track["file"], track["file"]],
        )
        play_item = FakePlayItem(track, "playlist", positions=[0, 1])
        manager = make_manager(
            self.playbackmanager, api, player, state, play_item=play_item
        )

        manager.launch_next_track()

        self.assertIs(state.playing_next, False)
        self.assertEqual(api.queue_calls, [])
        self.assertEqual(api.dequeue_calls, 0)
        self.assertEqual(api.play_addon_calls, 0)
        self.assertEqual(player.playnext_calls, 0)

    def test_playlist_source_is_overlay_only_when_countdown_completes(self):
        track = {
            "trackid": 5,
            "file": "http://127.0.0.1:52309/track/def/180.wav",
            "duration": 180,
        }
        state = FakeState(queued=True)
        api = FakeApi(has_addon_data=True, notification_time=15, queue_result=True)
        player = FakePlayer(
            times=[90, 99],
            totals=[100, 100],
            playing=[True, False],
            files=[track["file"], track["file"]],
        )
        manager = make_manager(self.playbackmanager, api, player, state)

        play_next, keep_playing = manager.launch_popup(track, source="playlist")

        self.assertIs(play_next, False)
        self.assertIs(keep_playing, True)
        self.assertEqual(api.queue_calls, [])
        self.assertEqual(api.dequeue_calls, 0)
        self.assertEqual(api.play_addon_calls, 0)
        self.assertEqual(player.playnext_calls, 0)

    def test_non_playlist_countdown_completion_still_plays_queued_item(self):
        track = {"trackid": 6, "duration": 180}
        state = FakeState()
        api = FakeApi(has_addon_data=False, notification_time=15, queue_result=True)
        player = FakePlayer(
            times=[90, 99],
            totals=[100, 100],
            playing=[True, False],
            files=["library-track.mp3", "library-track.mp3"],
        )
        manager = make_manager(self.playbackmanager, api, player, state)

        play_next, keep_playing = manager.launch_popup(track, source="library")

        self.assertIs(play_next, True)
        self.assertIs(keep_playing, True)
        self.assertEqual(api.queue_calls, [track])
        self.assertEqual(player.playnext_calls, 1)


if __name__ == "__main__":
    unittest.main()
