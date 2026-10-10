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
    "monitor",
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

        result = manager.launch_popup(
            {"trackid": 2, "duration": 180}, source="library"
        )

        self.assertEqual(result, self.playbackmanager.POPUP_ABORTED)
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

        result = manager.launch_popup(
            {"trackid": 3, "duration": 180}, source="library"
        )

        self.assertEqual(result, self.playbackmanager.POPUP_CLOSED)
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

        result = manager.launch_popup(
            {"trackid": "next", "duration": 180}, source="addon"
        )

        self.assertEqual(result, self.playbackmanager.POPUP_CLOSED)
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

        result = manager.launch_popup(track, source="playlist")

        self.assertEqual(result, self.playbackmanager.POPUP_DONE)
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

        result = manager.launch_popup(track, source="library")

        self.assertEqual(result, self.playbackmanager.POPUP_PLAYED)
        self.assertEqual(api.queue_calls, [track])
        self.assertEqual(player.playnext_calls, 1)

    def test_rewind_out_of_trigger_zone_keeps_queue_and_addon_data_for_rearm(self):
        track = {"trackid": 7, "duration": 180}
        state = FakeState()
        api = FakeApi(has_addon_data=False, notification_time=15, queue_result=True)
        player = FakePlayer(
            times=[85, 70],
            totals=[100, 100],
            playing=[True],
            files=["library-track.mp3", "library-track.mp3"],
        )
        play_item = FakePlayItem(track, "library")
        manager = make_manager(
            self.playbackmanager, api, player, state, play_item=play_item
        )

        result = manager.launch_next_track()

        self.assertEqual(result, self.playbackmanager.POPUP_ABORTED)
        self.assertEqual(api.queue_calls, [track])
        self.assertEqual(api.dequeue_calls, 0)
        self.assertEqual(api.reset_calls, 0)
        self.assertIs(state.queued, True)
        self.assertEqual(player.stop_calls, 0)

        # Re-armed popup for the same track must not queue the item twice.
        player._times = [90, 99]
        player._playing = [True, False]
        result = manager.launch_next_track()

        self.assertEqual(result, self.playbackmanager.POPUP_PLAYED)
        self.assertEqual(api.queue_calls, [track])
        self.assertEqual(player.playnext_calls, 1)

    def test_countdown_error_still_closes_widget(self):
        state = FakeState()
        api = FakeApi(has_addon_data=False, notification_time=15, queue_result=True)
        player = FakePlayer(
            times=[90, 95],
            totals=[100, 100],
            playing=[True],
            files=["library-track.mp3", "library-track.mp3"],
        )
        manager = make_manager(self.playbackmanager, api, player, state)

        def explode(**_kwargs):
            raise ValueError("boom")

        original_init = self.widgets.__init__

        def init(widget):
            original_init(widget)
            widget.update_progress_control = explode

        self.widgets.__init__ = init
        with self.assertRaises(ValueError):
            manager.launch_popup({"trackid": 8, "duration": 180}, source="library")

        self.assertEqual(self.widgets.instances[-1].close_calls, 1)


class MonitorResilienceTests(unittest.TestCase):
    def setUp(self):
        self._module_names = KODI_MODULES + RUNTIME_MODULES
        self._original_modules = {
            name: sys.modules.get(name, MISSING) for name in self._module_names
        }
        for module_name in self._module_names:
            sys.modules.pop(module_name, None)
        self._original_path = list(sys.path)
        sys.path.insert(0, str(LIB_DIR))
        install_kodi_mocks()
        self.monitor = importlib.import_module("monitor")

    def tearDown(self):
        for module_name in self._module_names:
            original = self._original_modules[module_name]
            if original is MISSING:
                sys.modules.pop(module_name, None)
            else:
                sys.modules[module_name] = original
        sys.path[:] = self._original_path

    def test_unexpected_error_is_logged_and_service_keeps_running(self):
        events = []
        ticks = iter([False, False, True])
        service = self.monitor.NextTrackMonitor.__new__(self.monitor.NextTrackMonitor)

        class Player(object):
            def disable_tracking(self):
                events.append("disable")

            def reset_queue(self):
                events.append("reset_queue")

        class Api(object):
            def reset_addon_data(self):
                events.append("reset_data")

        def boom():
            events.append("check")
            raise ValueError("boom")

        service.player = Player()
        service.api = Api()
        service.abortRequested = lambda: False
        service.waitForAbort = lambda _timeout: next(ticks)
        service._check_playback = boom

        service.run()

        self.assertEqual(events.count("check"), 2)
        self.assertEqual(events.count("disable"), 2)
        self.assertEqual(events.count("reset_queue"), 2)
        self.assertEqual(events.count("reset_data"), 2)


    def test_unexpected_error_clears_nexttrack_window_properties(self):
        utils = importlib.import_module("utils")
        nexttrack = importlib.import_module("nexttrack")
        for key in nexttrack.PROPERTY_KEYS:
            utils.set_property(nexttrack.PROP_PREFIX + key, "stale")
        utils.set_property(nexttrack.DIALOG_PROPERTY, "true")
        ticks = iter([False, True])
        service = self.monitor.NextTrackMonitor.__new__(self.monitor.NextTrackMonitor)

        class Player(object):
            def disable_tracking(self):
                pass

            def reset_queue(self):
                pass

        class Api(object):
            def reset_addon_data(self):
                pass

        def boom():
            raise ValueError("boom")

        service.player = Player()
        service.api = Api()
        service.abortRequested = lambda: False
        service.waitForAbort = lambda _timeout: next(ticks)
        service._check_playback = boom

        service.run()

        for key in nexttrack.PROPERTY_KEYS:
            self.assertEqual(utils.get_property(nexttrack.PROP_PREFIX + key), "")
        self.assertEqual(utils.get_property(nexttrack.DIALOG_PROPERTY), "")

    def _service_in_trigger_zone(self, popup_result):
        service = self.monitor.NextTrackMonitor.__new__(self.monitor.NextTrackMonitor)

        class Player(object):
            def __init__(self):
                self.last_file = None
                self.tracking = True
                self.last_file_history = []

            def is_tracking(self):
                return self.tracking

            def disable_tracking(self):
                self.tracking = False

            def isExternalPlayer(self):
                return False

            def get_last_file(self):
                return self.last_file

            def set_last_file(self, filename):
                self.last_file = filename
                self.last_file_history.append(filename)

            playing_file = "song.mp3"

            def getPlayingFile(self):
                return self.playing_file

            def getTotalTime(self):
                return 200

            def getTime(self):
                return 190

        class Api(object):
            def notification_time(self, total_time=None):
                return 15

        class Manager(object):
            calls = 0

            def launch_next_track(self):
                Manager.calls += 1
                return popup_result

        service.player = Player()
        service.api = Api()
        service.playback_manager = Manager()
        return service

    def test_aborted_popup_rearms_tracking_for_same_file(self):
        service = self._service_in_trigger_zone(
            importlib.import_module("playbackmanager").POPUP_ABORTED
        )

        service._check_playback()

        self.assertIs(service.player.tracking, True)
        self.assertEqual(service.player.last_file_history, ["song.mp3", None])
        service._check_playback()
        self.assertEqual(service.playback_manager.calls, 2)

    def test_completed_popup_stops_tracking_for_file(self):
        service = self._service_in_trigger_zone(
            importlib.import_module("playbackmanager").POPUP_PLAYED
        )

        service._check_playback()

        self.assertIs(service.player.tracking, False)
        self.assertEqual(service.player.last_file, "song.mp3")

    def test_crossfaded_next_track_stays_tracked(self):
        playbackmanager = importlib.import_module("playbackmanager")
        service = self._service_in_trigger_zone(playbackmanager.POPUP_CLOSED)

        def launch():
            # The next song started (and enabled tracking) during the countdown
            service.player.playing_file = "next.mp3"
            return playbackmanager.POPUP_CLOSED

        service.playback_manager.launch_next_track = launch
        service._check_playback()

        self.assertIs(service.player.tracking, True)

    def test_missing_next_track_is_looked_up_again(self):
        monitor = self.monitor
        service = self._service_in_trigger_zone(None)
        now = [1000.0]
        original = monitor.time.monotonic
        monitor.time.monotonic = lambda: now[0]
        self.addCleanup(setattr, monitor.time, "monotonic", original)

        service._check_playback()
        self.assertIs(service.player.tracking, True)
        self.assertIsNone(service.player.last_file)
        service._check_playback()  # throttled
        self.assertEqual(service.playback_manager.calls, 1)
        now[0] += monitor.NO_NEXT_RETRY_SECS
        service._check_playback()
        self.assertEqual(service.playback_manager.calls, 2)

    def test_service_shares_one_player_instance(self):
        player_module = importlib.import_module("player")
        created = []
        original_init = player_module.NextTrackPlayer.__init__

        def counting_init(instance):
            created.append(instance)
            original_init(instance)

        player_module.NextTrackPlayer.__init__ = counting_init
        try:
            service = self.monitor.NextTrackMonitor()
        finally:
            player_module.NextTrackPlayer.__init__ = original_init

        self.assertEqual(len(created), 1)
        self.assertIs(service.playback_manager.player, service.player)
        self.assertIs(service.playback_manager.play_item.player, service.player)


class PlaylistPositionTests(unittest.TestCase):
    def setUp(self):
        self._module_names = KODI_MODULES + RUNTIME_MODULES
        self._original_modules = {
            name: sys.modules.get(name, MISSING) for name in self._module_names
        }
        for module_name in self._module_names:
            sys.modules.pop(module_name, None)
        self._original_path = list(sys.path)
        sys.path.insert(0, str(LIB_DIR))
        install_kodi_mocks()
        self.playitem = importlib.import_module("playitem")

    def tearDown(self):
        for module_name in self._module_names:
            original = self._original_modules[module_name]
            if original is MISSING:
                sys.modules.pop(module_name, None)
            else:
                sys.modules[module_name] = original
        sys.path[:] = self._original_path

    def position(self, position, size, conditions=()):
        class PlayList(object):
            def __init__(self, _playlist_id):
                pass

            def getposition(self):
                return position

            def size(self):
                return size

        self.playitem.PlayList = PlayList
        self.playitem.getCondVisibility = lambda condition: condition in conditions
        item = self.playitem.PlayItem()
        item.api = type("Api", (), {"get_playlistid": lambda self: 0})()
        return item.get_playlist_position()

    def test_next_position(self):
        self.assertEqual(1, self.position(0, 3))
        self.assertIsNone(self.position(2, 3))

    def test_repeat_all_wraps_to_the_first_item(self):
        self.assertEqual(0, self.position(2, 3, ("Playlist.IsRepeat",)))

    def test_repeat_one_plays_nothing_else_next(self):
        self.assertIsNone(self.position(0, 3, ("Playlist.IsRepeatOne",)))


class NextTrackDialogTests(unittest.TestCase):
    def setUp(self):
        self._module_names = KODI_MODULES + RUNTIME_MODULES
        self._original_modules = {
            name: sys.modules.get(name, MISSING) for name in self._module_names
        }
        for module_name in self._module_names:
            sys.modules.pop(module_name, None)
        self._original_path = list(sys.path)
        sys.path.insert(0, str(LIB_DIR))
        install_kodi_mocks()
        self.xbmc = sys.modules["xbmc"]
        self.builtins = []
        self.logs = []
        self.xbmc.executebuiltin = self.builtins.append
        self.xbmc.log = lambda msg, level=None: self.logs.append(level)
        self.nexttrack = importlib.import_module("nexttrack")

    def tearDown(self):
        for module_name in self._module_names:
            original = self._original_modules[module_name]
            if original is MISSING:
                sys.modules.pop(module_name, None)
            else:
                sys.modules[module_name] = original
        sys.path[:] = self._original_path

    def test_action_ids_match_kodi_action_names(self):
        expected = {
            1: "Left", 2: "Right", 3: "Up", 4: "Down", 7: "Select",
            9: "ParentFolder", 10: "PreviousMenu", 11: "Info", 12: "Pause",
            13: "Stop", 14: "SkipNext", 15: "SkipPrevious", 18: "FullScreen",
            58: "Number0", 67: "Number9", 77: "FastForward", 78: "Rewind",
            79: "Play", 85: "Screenshot", 88: "VolumeUp", 89: "VolumeDown",
            91: "Mute", 92: "Back", 117: "ContextMenu", 229: "PlayPause",
        }
        for action_id, name in expected.items():
            self.assertEqual(self.nexttrack.ACTION_ID_TO_NAME.get(action_id), name)
        for unmapped in (16, 17, 107):
            self.assertNotIn(unmapped, self.nexttrack.ACTION_ID_TO_NAME)

    def test_on_action_forwards_by_name_and_logs_at_debug(self):
        class Action(object):
            def __init__(self, action_id):
                self.action_id = action_id

            def getId(self):
                return self.action_id

        dialog = self.nexttrack.NextTrackDialog("script-nexttrack-nexttrack.xml")
        dialog.set_underlying_window_id(12006)

        dialog.onAction(Action(11))
        dialog.onAction(Action(14))

        self.assertEqual(self.builtins, ["Action(Info,12006)", "Action(SkipNext,12006)"])
        self.assertEqual(set(self.logs), {self.xbmc.LOGDEBUG})

    def test_progress_follows_the_real_time_left(self):
        utils = importlib.import_module("utils")
        widget = self.nexttrack.NextTrack()
        widget.set_item({"title": "Song"})
        widget.set_progress_step_size(1.0)
        widget.show()
        widget.update_progress_control(remaining=5, period=10)
        self.assertEqual(utils.get_property("NextTrack.progress"), "50")
        widget.close()

    def test_close_clears_properties_even_if_dialog_close_fails(self):
        utils = importlib.import_module("utils")
        widget = self.nexttrack.NextTrack()
        widget.set_item({"title": "Song", "artist": "Artist"})
        widget.show()
        self.assertEqual(utils.get_property("NextTrack.IsVisible"), "true")

        class BrokenDialog(object):
            def close(self):
                raise RuntimeError("dialog gone")

        widget._dialog = BrokenDialog()
        with self.assertRaises(RuntimeError):
            widget.close()

        for key in self.nexttrack.PROPERTY_KEYS:
            self.assertEqual(utils.get_property("NextTrack." + key), "")
        self.assertEqual(utils.get_property("service.nexttrack.dialog"), "")


if __name__ == "__main__":
    unittest.main()
