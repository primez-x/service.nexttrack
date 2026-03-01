# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)
"""Next Track test/demo script."""

from __future__ import absolute_import, division, unicode_literals
import xbmc
from xbmc import Monitor, executebuiltin
from nexttrack import NextTrack


def test_popup(_window_arg=None):
    """Show a demo Next Track widget using the property-based overlay."""
    executebuiltin('Dialog.Close(addonsettings,true)')
    xbmc.sleep(300)

    nt = NextTrack()
    nt.set_item({
        'title': 'Bohemian Rhapsody',
        'artist': 'Queen',
        'album': 'A Night at the Opera',
        'art': {
            'thumb': 'https://i.scdn.co/image/ab67616d0000b273e8b066f70c206551210d902b',
            'landscape': 'https://i.scdn.co/image/ab67616d0000b273e8b066f70c206551210d902b',
            'fanart': 'https://i.scdn.co/image/ab67616d0000b273e8b066f70c206551210d902b',
        },
        'year': '1975',
        'rating': '9.2',
        'playcount': 42,
        'runtime': 354,
    })
    nt.set_progress_step_size(1.0)
    nt.show()

    step = 0
    wait_s = 0.5
    timeout_steps = 20  # 10 seconds at 500 ms
    monitor = Monitor()
    remaining = 10
    while step < timeout_steps and not monitor.abortRequested():
        monitor.waitForAbort(wait_s)
        remaining = max(0, 10 - step // 2)
        nt.update_progress_control(remaining=remaining, runtime=remaining)
        step += 1

    nt.close()

    executebuiltin('Addon.OpenSettings(service.nexttrack)')


def open_settings():
    from xbmcaddon import Addon
    Addon().openSettings()


def run(argv):
    """Route to API method."""
    if len(argv) >= 2 and argv[1] == 'test_window':
        test_popup()
    else:
        open_settings()
