# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)
"""Next Track test/demo script."""

from __future__ import absolute_import, division, unicode_literals
from datetime import datetime, timedelta
from math import ceil
from xbmc import Monitor
from xbmcgui import WindowXMLDialog
from statichelper import from_unicode
from utils import addon_path, localize, localize_time


class TestPopup(WindowXMLDialog):
    ACTION_PLAYER_STOP = 13
    ACTION_NAV_BACK = 92
    progress_step_size = 0
    current_progress_percent = 100.0
    progress_control = None
    pause = False

    def onInit(self):  # pylint: disable=invalid-name
        self.set_info()
        self.prepare_progress_control()
        self.getControl(3013).setLabel(localize(30034))  # Close

    def set_info(self):
        self.setProperty('thumb', 'https://i.scdn.co/image/ab67616d0000b273e8b066f70c206551210d902b')
        self.setProperty('fanart', 'https://i.scdn.co/image/ab67616d0000b273e8b066f70c206551210d902b')
        self.setProperty('landscape', 'https://i.scdn.co/image/ab67616d0000b273e8b066f70c206551210d902b')

        self.setProperty('title', 'Bohemian Rhapsody')
        self.setProperty('artist', 'Queen')
        self.setProperty('album', 'A Night at the Opera')
        self.setProperty('year', '1975')
        self.setProperty('rating', '9.2')
        self.setProperty('playcount', '42')
        self.setProperty('runtime', '354')

    def prepare_progress_control(self):
        try:
            self.progress_control = self.getControl(3014)
        except RuntimeError:
            return
        self.progress_control.setPercent(100.0)  # pylint: disable=no-member,useless-suppression

    def update_progress_control(self, timeout, wait):
        if self.progress_control is None:
            return
        self.current_progress_percent -= 100 * wait / timeout
        self.progress_control.setPercent(self.current_progress_percent)  # pylint: disable=no-member,useless-suppression
        self.setProperty('remaining', from_unicode('%02d' % ceil((timeout / 1000) * (self.current_progress_percent / 100))))
        self.setProperty('endtime', from_unicode(localize_time(datetime.now() + timedelta(seconds=354))))

    def onFocus(self, controlId):  # pylint: disable=invalid-name,unused-argument
        pass

    def doAction(self):  # pylint: disable=invalid-name
        pass

    def closeDialog(self):  # pylint: disable=invalid-name
        self.close()

    def onClick(self, controlId):  # pylint: disable=invalid-name,unused-argument
        self.close()

    def onAction(self, action):  # pylint: disable=invalid-name
        if action == self.ACTION_PLAYER_STOP:
            self.close()
        elif action == self.ACTION_NAV_BACK:
            self.close()


def test_popup(window):
    popup = TestPopup(window, addon_path(), 'default', '1080i')
    popup.show()
    step = 0
    wait = 100
    wait_s = wait / 1000
    timeout = 10000
    monitor = Monitor()
    while popup and step < timeout and not monitor.abortRequested():
        if popup.pause:
            continue
        monitor.waitForAbort(wait_s)
        popup.update_progress_control(timeout, wait)
        step += wait


def open_settings():
    from xbmcaddon import Addon
    Addon().openSettings()


def run(argv):
    """Route to API method."""
    if len(argv) == 3 and argv[1] == 'test_window':
        test_popup(argv[2])
    else:
        open_settings()
