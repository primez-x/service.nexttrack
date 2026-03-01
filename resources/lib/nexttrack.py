# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)

from __future__ import absolute_import, division, unicode_literals
from datetime import datetime, timedelta
from statichelper import from_unicode
from utils import localize_time, set_property, clear_property

PROP_PREFIX = 'NextTrack.'


class NextTrack:
    """Non-blocking next-track overlay driven by Home window properties.

    Instead of opening a modal dialog, this sets properties on window 10000
    that the skin reads to render a non-blocking widget.
    """

    def __init__(self):
        self.item = None
        self.cancel = False
        self.progress_step_size = 0
        self.current_progress_percent = 100
        self._last_remaining = None
        self._last_endtime = None

    def set_item(self, item):
        self.item = item

    def set_progress_step_size(self, progress_step_size):
        self.progress_step_size = progress_step_size

    def show(self):
        """Publish track info as Home window properties for the skin to display."""
        self._set_info()
        set_property(PROP_PREFIX + 'progress', '100')
        set_property('service.nexttrack.dialog', 'true')

    def close(self):
        """Clear all properties so the skin hides the widget."""
        clear_property('service.nexttrack.dialog')
        for key in ('title', 'artist', 'album', 'thumb', 'fanart', 'landscape',
                     'clearart', 'clearlogo', 'poster', 'year', 'rating',
                     'playcount', 'runtime', 'remaining', 'endtime', 'progress'):
            clear_property(PROP_PREFIX + key)

    def _set_info(self):
        item = self.item or {}

        art = item.get('art', {}) or {}
        set_property(PROP_PREFIX + 'fanart', art.get('fanart', ''))
        set_property(PROP_PREFIX + 'landscape', art.get('landscape', ''))
        set_property(PROP_PREFIX + 'clearart', art.get('clearart', ''))
        set_property(PROP_PREFIX + 'clearlogo', art.get('clearlogo', ''))
        set_property(PROP_PREFIX + 'poster', art.get('poster', ''))
        set_property(PROP_PREFIX + 'thumb', art.get('thumb', ''))

        title = item.get('title', '')
        artist = item.get('artist', '')
        if isinstance(artist, list):
            artist = ', '.join(artist)
        album = item.get('album', '')

        set_property(PROP_PREFIX + 'artist', artist)
        set_property(PROP_PREFIX + 'album', album)
        set_property(PROP_PREFIX + 'title', title)

        year = item.get('year') or ''
        set_property(PROP_PREFIX + 'year', from_unicode(str(year)))

        rating_val = item.get('rating')
        if rating_val is None:
            rating = ''
        else:
            try:
                rating = str(round(float(rating_val), 1))
            except (TypeError, ValueError):
                rating = from_unicode('%s' % rating_val)
        set_property(PROP_PREFIX + 'rating', rating)

        set_property(PROP_PREFIX + 'playcount', from_unicode(str(item.get('playcount', 0))))

        runtime = item.get('runtime') or item.get('duration') or 0
        set_property(PROP_PREFIX + 'runtime', from_unicode(str(runtime)))

    def update_progress_control(self, remaining=None, runtime=None):
        self.current_progress_percent = max(0, self.current_progress_percent - self.progress_step_size)
        set_property(PROP_PREFIX + 'progress', str(int(self.current_progress_percent)))
        if remaining is not None and remaining != self._last_remaining:
            self._last_remaining = remaining
            set_property(PROP_PREFIX + 'remaining', from_unicode('%02d' % remaining))
        if runtime is not None:
            endtime_str = from_unicode(localize_time(datetime.now() + timedelta(seconds=runtime)))
            if endtime_str != self._last_endtime:
                self._last_endtime = endtime_str
                set_property(PROP_PREFIX + 'endtime', endtime_str)

    def set_cancel(self, cancel):
        self.cancel = cancel

    def is_cancel(self):
        return self.cancel
