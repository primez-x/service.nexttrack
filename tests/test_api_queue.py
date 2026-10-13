from __future__ import absolute_import, division, unicode_literals

import importlib
import sys
import types
import unittest
from pathlib import Path


LIB_DIR = Path(__file__).resolve().parents[1] / "resources" / "lib"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))


class FakePlaylist(object):
    """Playlist whose contents the test controls; Add appends, Remove pops."""
    items = []

    def __init__(self, _playlist_id):
        pass

    def size(self):
        return len(FakePlaylist.items)


def install_mocks(calls):
    xbmc = types.ModuleType("xbmc")
    xbmc.LOGDEBUG = 0
    xbmc.LOGINFO = 1
    xbmc.PLAYLIST_MUSIC = 0
    xbmc.PLAYLIST_VIDEO = 1
    xbmc.sleep = lambda _ms: None
    xbmc.log = lambda *_a, **_k: None
    xbmc.executebuiltin = lambda *_a, **_k: None
    xbmc.getCondVisibility = lambda _c: False
    xbmc.getInfoLabel = lambda label: "20.0" if label == "System.BuildVersion" else ""
    xbmc.getRegion = lambda _key: "%H:%M"
    xbmc.executeJSONRPC = lambda _payload: "{}"
    xbmc.PlayList = FakePlaylist

    xbmcaddon = types.ModuleType("xbmcaddon")

    class MockAddon(object):
        def getAddonInfo(self, key):
            return {"id": "service.nexttrack", "path": ""}.get(key, "")

        def getSetting(self, _key):
            return ""

        def getSettingBool(self, _key):
            return False

        def getSettingInt(self, key):
            return 15 if key == 'notificationSeconds' else 2

        def getLocalizedString(self, string_id):
            return str(string_id)

    xbmcaddon.Addon = MockAddon

    xbmcgui = types.ModuleType("xbmcgui")

    class MockWindow(object):
        def __init__(self, _window_id):
            pass

        def getProperty(self, _key):
            return ""

        def setProperty(self, _key, _value):
            pass

        def clearProperty(self, _key):
            pass

    xbmcgui.Window = MockWindow
    sys.modules["xbmc"] = xbmc
    sys.modules["xbmcaddon"] = xbmcaddon
    sys.modules["xbmcgui"] = xbmcgui

    for name in ("api", "utils", "statichelper"):
        sys.modules.pop(name, None)
    api = importlib.import_module("api")
    api.Api._shared_state.clear()
    api.Api.clear_caches()
    api.Api.queued_position = None

    def fake_jsonrpc(method=None, id=None, params=None, **_kwargs):  # pylint: disable=redefined-builtin
        calls.append((method, params))
        if method == 'Player.GetActivePlayers':
            return {'result': [{'playerid': 0, 'type': 'audio'}]}
        if method == 'Player.GetProperties':
            return {'result': {'playlistid': 0}}
        if method == 'Playlist.Add':
            FakePlaylist.items.append(params['item'])
        if method == 'Playlist.Remove':
            position = params['position']
            if 0 <= position < len(FakePlaylist.items):
                FakePlaylist.items.pop(position)
        return {'result': {}}

    api.jsonrpc = fake_jsonrpc
    return api


class ApiQueueTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.api = install_mocks(self.calls)
        FakePlaylist.items = [{'file': 'a'}, {'file': 'b'}, {'file': 'current'}]

    def test_dequeue_removes_the_appended_track_not_position_1(self):
        api = self.api.Api()
        track = {'trackid': 42, 'file': 'next'}

        self.assertTrue(api.queue_next_item(track))
        self.assertEqual(api.queued_position, 3)
        self.assertEqual(len(FakePlaylist.items), 4)

        self.assertFalse(api.dequeue_next_item())
        self.assertEqual([i.get('file') for i in FakePlaylist.items],
                         ['a', 'b', 'current'])
        self.assertIsNone(api.queued_position)

    def test_track_without_valid_id_is_not_queued(self):
        api = self.api.Api()
        self.assertFalse(api.queue_next_item({'trackid': -1}))
        self.assertFalse(api.queue_next_item({'trackid': None}))
        self.assertFalse(api.queue_next_item({}))
        self.assertEqual(len(FakePlaylist.items), 3)

    def test_failed_add_does_not_claim_or_remove_a_playlist_item(self):
        original_jsonrpc = self.api.jsonrpc

        def failed_add(method=None, id=None, params=None, **kwargs):  # pylint: disable=redefined-builtin
            if method == 'Playlist.Add':
                self.calls.append((method, params))
                return {'error': {'code': -1, 'message': 'Playlist.Add failed'}}
            return original_jsonrpc(method=method, id=id, params=params, **kwargs)

        self.api.jsonrpc = failed_add
        api = self.api.Api()

        self.assertFalse(api.queue_next_item({'trackid': 42}))
        self.assertIsNone(api.queued_position)
        self.assertFalse(api.dequeue_next_item())
        self.assertFalse(any(method == 'Playlist.Remove' for method, _ in self.calls))

    def test_dequeue_without_owned_item_does_not_remove_a_playlist_entry(self):
        api = self.api.Api()

        self.assertFalse(api.dequeue_next_item())
        self.assertFalse(any(method == 'Playlist.Remove' for method, _ in self.calls))

    def test_invalid_provider_notification_time_is_ignored(self):
        api = self.api.Api()
        api.data = {'notification_time': 'soon'}
        self.assertEqual(api.notification_time(total_time=200), 15)
        api.data = {'notification_time': '30'}
        self.assertEqual(api.notification_time(total_time=200), 30)
        api.data = {'notification_offset': 'late'}
        self.assertEqual(api.notification_time(total_time=200), 15)


if __name__ == "__main__":
    unittest.main()
