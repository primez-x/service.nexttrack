# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)

from __future__ import absolute_import, division, unicode_literals
from datetime import datetime, timedelta
from platform import machine
from xbmc import Player
from xbmcgui import WindowXMLDialog
from statichelper import from_unicode
from utils import localize_time

ACTION_PLAYER_STOP = 13
ACTION_NAV_BACK = 92
OS_MACHINE = machine()


class NextTrack(WindowXMLDialog):
    item = None
    cancel = False
    progress_step_size = 0
    current_progress_percent = 100

    def __init__(self, *args, **kwargs):
        self.action_exitkeys_id = [10, 13]
        self.progress_control = None
        if OS_MACHINE[0:5] == 'armv7':
            WindowXMLDialog.__init__(self)
        else:
            WindowXMLDialog.__init__(self, *args, **kwargs)

    def onInit(self):  # pylint: disable=invalid-name
        self.set_info()
        self.prepare_progress_control()

    def set_info(self):
        """Populate window properties from the provided track item."""
        item = self.item or {}

        art = item.get('art', {}) or {}

        self.setProperty('fanart', art.get('fanart', ''))
        self.setProperty('landscape', art.get('landscape', ''))
        self.setProperty('clearart', art.get('clearart', ''))
        self.setProperty('clearlogo', art.get('clearlogo', ''))
        self.setProperty('poster', art.get('poster', ''))
        self.setProperty('thumb', art.get('thumb', ''))

        title = item.get('title', '')
        artist = item.get('artist', '')
        if isinstance(artist, list):
            artist = ', '.join(artist)
        album = item.get('album', '')

        self.setProperty('artist', artist)
        self.setProperty('album', album)
        self.setProperty('title', title)

        year = item.get('year') or ''
        self.setProperty('year', from_unicode(str(year)))

        rating_val = item.get('rating')
        if rating_val is None:
            rating = ''
        else:
            try:
                rating = str(round(float(rating_val), 1))
            except (TypeError, ValueError):
                rating = from_unicode('%s' % rating_val)
        self.setProperty('rating', rating)

        self.setProperty('playcount', from_unicode(str(item.get('playcount', 0))))

        runtime = item.get('runtime') or item.get('duration') or 0
        self.setProperty('runtime', from_unicode(str(runtime)))

    def prepare_progress_control(self):
        try:
            self.progress_control = self.getControl(3014)
        except RuntimeError:
            pass
        else:
            self.progress_control.setPercent(self.current_progress_percent)  # pylint: disable=no-member,useless-suppression

    def set_item(self, item):
        self.item = item

    def set_progress_step_size(self, progress_step_size):
        self.progress_step_size = progress_step_size

    def update_progress_control(self, remaining=None, runtime=None):
        self.current_progress_percent = self.current_progress_percent - self.progress_step_size
        try:
            self.progress_control = self.getControl(3014)
        except RuntimeError:
            pass
        else:
            self.progress_control.setPercent(self.current_progress_percent)  # pylint: disable=no-member,useless-suppression

        if remaining:
            self.setProperty('remaining', from_unicode('%02d' % remaining))
        if runtime:
            self.setProperty('endtime', from_unicode(localize_time(datetime.now() + timedelta(seconds=runtime))))

    def set_cancel(self, cancel):
        self.cancel = cancel

    def is_cancel(self):
        return self.cancel

    def onFocus(self, controlId):  # pylint: disable=invalid-name,unused-argument
        pass

    def doAction(self):  # pylint: disable=invalid-name
        pass

    def closeDialog(self):  # pylint: disable=invalid-name
        self.close()

    def onClick(self, controlId):  # pylint: disable=invalid-name
        if controlId == 3013:
            self.set_cancel(True)
            self.close()

    def onAction(self, action):  # pylint: disable=invalid-name
        if action == ACTION_PLAYER_STOP:
            self.close()
        elif action == ACTION_NAV_BACK:
            self.set_cancel(True)
            self.close()
