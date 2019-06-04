# Copyright (C) 2014 Science and Technology Facilities Council.
# Copyright (C) 2015 East Asian Observatory.
# All Rights Reserved.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import absolute_import, division, print_function, \
    unicode_literals

import os

from hedwig import config

from .compat import TestCase


class DummyConfigTestCase(TestCase):
    def setUp(self):
        self._clear_config()

        # Store a copy of the config file path tuple and append
        # '.template' to the last component in case we are testing
        # in a fresh copy of the application with no customized config
        # file.
        self.orig_file = config.config_file
        if not self.orig_file[-1].endswith('.template'):
            config.config_file = self.orig_file[:-1] + (
                self.orig_file[-1] + '.template',)

    def tearDown(self):
        # Same clean-up as setUp().
        self._clear_config()

        # Restore config file path tuple.
        config.config_file = self.orig_file

    def _clear_config(self):
        # Unload existing configuation.
        config.config = None
        config.database = None
        config.facilities = None

        # Unset home directory variable.
        if 'HEDWIG_DIR' in os.environ:
            del os.environ['HEDWIG_DIR']
