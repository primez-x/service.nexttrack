# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)

from __future__ import absolute_import, division, unicode_literals
import os
from datetime import datetime, timedelta
import xbmc
import xbmcgui
import xbmcvfs
from statichelper import from_unicode
from utils import addon_path, localize_time, set_property, clear_property

PROP_PREFIX = 'NextTrack.'

# Map numeric action IDs to Kodi action names for executebuiltin
ACTION_ID_TO_NAME = {
    1: 'Left',
    2: 'Right',
    3: 'Up',
    4: 'Down',
    5: 'PageUp',
    6: 'PageDown',
    7: 'Select',
    9: 'ParentDir',
    10: 'PreviousMenu',
    11: 'TakeScreenshot',
    12: 'Pause',
    13: 'Stop',
    14: 'SkipPrevious',
    15: 'SkipNext',
    16: 'FullScreen',
    17: 'AspectRatio',
    18: 'StepBack',
    19: 'StepForward',
    20: 'BigStepBack',
    21: 'BigStepForward',
    22: 'OSD',
    23: 'ShowSubtitles',
    24: 'PlayPause',
    25: 'Decrease',
    26: 'Increase',
    27: 'Info',
    28: 'NextPicture',
    29: 'PreviousPicture',
    30: 'CycleCaption',
    31: 'Language',
    32: 'VolumePlus',
    33: 'VolumeMinus',
    34: 'VolumeAmplify',
    35: 'VolumeAmplifyRelease',
    36: 'Mute',
    37: 'CycleResolution',
    38: 'CycleAudioChannel',
    39: 'VerticalShift',
    40: 'VerticalShiftUp',
    41: 'VerticalShiftDown',
    42: 'NextSubtitleStream',
    43: 'PreviousSubtitleStream',
    44: 'OpenSubtitles',
    45: 'Backspace',
    46: 'Tab',
    47: 'Return',
    48: 'CapsLock',
    49: 'Escape',
    50: 'Space',
    51: 'Home',
    52: 'End',
    53: 'Insert',
    54: 'Delete',
    55: 'Menu',
    56: 'ContextMenu',
    57: 'Number0',
    58: 'Number1',
    59: 'Number2',
    60: 'Number3',
    61: 'Number4',
    62: 'Number5',
    63: 'Number6',
    64: 'Number7',
    65: 'Number8',
    66: 'Number9',
    67: 'F1',
    68: 'F2',
    69: 'F3',
    70: 'F4',
    71: 'F5',
    72: 'F6',
    73: 'F7',
    74: 'F8',
    75: 'F9',
    76: 'F10',
    77: 'F11',
    78: 'F12',
    79: 'Play',
    80: 'PlayPause',
    81: 'Record',
    82: 'Print',
    83: 'PrintScreen',
    84: 'Delete',
    85: 'Rewind',
    86: 'Forward',
    87: 'VolumeUp',
    88: 'VolumeUp',
    89: 'VolumeDown',
    90: 'ChannelUp',
    91: 'Mute',
    92: 'Back',
    107: 'Left',  # Sometimes mapped to this
}


class NextTrackDialog(xbmcgui.WindowXMLDialog):
    """Non-modal standalone overlay for skins without native Next Track support.

    Shown via show() (non-blocking).  Properties are set directly on the window
    so the XML can reference them as Window.Property(*) without any skin dependency.
    """

    def __init__(self, *args, **kwargs):
        pass  # Kodi initialises the C++ WindowXMLDialog via __new__ using the
              # args passed at instantiation time; do not forward here.
        self._underlying_window_id = None

    def set_underlying_window_id(self, window_id):
        """Store the window ID of the underlying window for action dispatch."""
        self._underlying_window_id = window_id

    def set_item(self, item):
        """Populate artwork and metadata properties before show()."""
        art = item.get('art', {}) or {}
        self.setProperty('landscape', art.get('landscape', ''))
        self.setProperty('fanart', art.get('fanart', ''))
        self.setProperty('thumb', art.get('thumb', ''))

        artist = item.get('artist', '')
        if isinstance(artist, list):
            artist = ', '.join(artist)
        self.setProperty('artist', artist)
        self.setProperty('title', item.get('title', ''))
        self.setProperty('album', item.get('album', ''))
        year = item.get('year') or ''
        self.setProperty('year', from_unicode(str(year)))
        # Initialise progress at 100 so the circle ring starts full
        self.setProperty('progress', '100')

    def onAction(self, action):
        """Forward all input to underlying window; swallow Back to prevent overlay close."""
        action_id = action.getId()
        xbmc.log('[nexttrack] onAction: id=%d' % action_id, xbmc.LOGINFO)
        if action_id in (xbmcgui.ACTION_NAV_BACK, xbmcgui.ACTION_PREVIOUS_MENU):
            pass  # Swallow — overlay cannot be user-dismissed
        elif self._underlying_window_id is not None:
            # Convert numeric action ID to action name for executebuiltin
            action_name = ACTION_ID_TO_NAME.get(action_id)
            if action_name:
                # Dispatch directly to the underlying window by ID using action name
                xbmc.executebuiltin('Action(%s,%d)' % (action_name, self._underlying_window_id))

    def update_display(self, percent, remaining=None, endtime=None):
        """Update the progress ring, progress bar, and countdown label."""
        # Update circle ring image (Window.Property(progress) maps to p0.png-p100.png)
        self.setProperty('progress', str(int(percent)))
        if remaining is not None:
            self.setProperty('remaining', from_unicode('%02d' % remaining))
        if endtime is not None:
            self.setProperty('endtime', endtime)


class NextTrack:
    """Non-blocking next-track overlay driven by Home window properties.

    For skins with native Next Track support (detected by the presence of
    script-nexttrack-nexttrack.xml in the skin's resolution directory, e.g.
    Arctic Fuse 3) the skin renders the overlay itself from the
    Window(Home).Property(NextTrack.*) values we set here.

    For all other skins a standalone NextTrackDialog is opened via show()
    (non-modal) and driven directly via Python property/control updates.
    """

    def __init__(self):
        self.item = None
        self.cancel = False
        self.progress_step_size = 0
        self.current_progress_percent = 100
        self._last_remaining = None
        self._last_endtime = None
        self._dialog = None

    def set_item(self, item):
        self.item = item

    def set_progress_step_size(self, progress_step_size):
        self.progress_step_size = progress_step_size

    def show(self):
        """Publish track info and show the overlay."""
        self._set_info()
        set_property(PROP_PREFIX + 'progress', '100')
        set_property('service.nexttrack.dialog', 'true')

        # Open the standalone dialog for skins that don't provide their own overlay
        if not self._skin_has_nexttrack_support():
            try:
                self._dialog = NextTrackDialog(
                    'script-nexttrack-nexttrack.xml', addon_path(), 'default', '1080i'
                )
                self._dialog.set_item(self.item or {})
                self._dialog.set_underlying_window_id(xbmcgui.getCurrentWindowId())
                self._dialog.show()
            except Exception as e:  # pylint: disable=broad-except
                import xbmc as _xbmc
                _xbmc.log('[service.nexttrack] NextTrackDialog show() failed: %s' % e, _xbmc.LOGINFO)
                self._dialog = None

    def close(self):
        """Clear all properties and close the overlay."""
        if self._dialog:
            self._dialog.close()
            self._dialog = None
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
        percent = int(self.current_progress_percent)
        set_property(PROP_PREFIX + 'progress', str(percent))

        endtime_str = None
        if remaining is not None and remaining != self._last_remaining:
            self._last_remaining = remaining
            set_property(PROP_PREFIX + 'remaining', from_unicode('%02d' % remaining))
        if runtime is not None:
            endtime_str = from_unicode(localize_time(datetime.now() + timedelta(seconds=runtime)))
            if endtime_str != self._last_endtime:
                self._last_endtime = endtime_str
                set_property(PROP_PREFIX + 'endtime', endtime_str)

        if self._dialog:
            self._dialog.update_display(percent, remaining, endtime_str)

    def set_cancel(self, cancel):
        self.cancel = cancel

    def is_cancel(self):
        return self.cancel

    @staticmethod
    def _skin_has_nexttrack_support():
        """Return True if the active skin provides its own Next Track overlay.

        Checks for script-nexttrack-nexttrack.xml in the skin's resolution
        directories.  Present in Arctic Fuse 3 and any skin with native support.
        When found we skip the standalone dialog since the skin renders the overlay
        itself from Window(Home).Property(NextTrack.*) values.
        """
        skin_dir = xbmcvfs.translatePath('special://skin/')
        for res_dir in ('1080i', '1080p', '720p'):
            override = os.path.join(skin_dir, res_dir, 'script-nexttrack-nexttrack.xml')
            if os.path.exists(override):
                return True
        return False
