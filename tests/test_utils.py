# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)

from __future__ import absolute_import, division, unicode_literals

import unittest
import sys
from unittest.mock import patch

from test_api_queue import install_mocks


class UtilityTests(unittest.TestCase):
    def setUp(self):
        install_mocks([])
        self.utils = sys.modules['utils']

    def tearDown(self):
        self.utils.clear_setting_cache()

    def test_progress_steps_use_the_tick_interval(self):
        self.assertEqual(self.utils.calculate_progress_steps(10), 1.0)
        self.assertEqual(
            self.utils.calculate_progress_steps(10, update_interval_sec=2), 20.0
        )
        self.assertEqual(
            self.utils.calculate_progress_steps(0, update_interval_sec=2), 10.0
        )

    def test_cached_settings_are_read_once_until_cache_clear(self):
        reads = []

        class CountingAddon(object):
            @staticmethod
            def getSettingInt(key):  # pylint: disable=invalid-name
                reads.append(key)
                return 30

        with patch.object(self.utils, 'Addon', CountingAddon):
            self.assertEqual(self.utils.get_setting_int('autoPlaySeasonTime', cache=True), 30)
            self.assertEqual(self.utils.get_setting_int('autoPlaySeasonTime', cache=True), 30)
            self.assertEqual(reads, ['autoPlaySeasonTime'])
            self.utils.clear_setting_cache()
            self.assertEqual(self.utils.get_setting_int('autoPlaySeasonTime', cache=True), 30)
            self.assertEqual(reads, ['autoPlaySeasonTime'] * 2)

    def test_log_formats_variadic_arguments(self):
        with patch.object(self.utils, 'get_setting_int', return_value=0), \
                patch.object(self.utils, 'get_global_setting', return_value=False), \
                patch.object(self.utils, 'get_kodi_version', return_value=19.0), \
                patch.object(self.utils, 'xlog') as logged:
            self.utils.log('logged %s', 'mapping', name='Test', level=0)

        self.assertTrue(logged.call_args[0][0].endswith('Test -> logged mapping'))


if __name__ == '__main__':
    unittest.main()
