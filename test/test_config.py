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

from ConfigParser import SafeConfigParser
import os
from unittest import TestCase

from insertnamehere import config
from insertnamehere.error import Error


class ConfigTestCase(TestCase):
    def setUp(self):
        self._clear_config()

        # Store a copy of the config file path tuple and append
        # '.template' to the last component in case we are testing
        # in a fresh copy of the application with no customized config
        # file.
        self.orig_file = config.config_file
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

        # Unset home directory variable.
        if 'INSERTNAMEHERE_DIR' in os.environ:
            del os.environ['INSERTNAMEHERE_DIR']

    def test_database_config(self):
        c = config.get_config()

        self.assertIsInstance(c, SafeConfigParser)

        self.assertTrue(c.has_section('database'))
        self.assertTrue(c.has_option('database', 'url'))

    def test_home_var(self):
        """
        Test that we get an error if the file doesn't exists.

        Also checks that the environment variable is being read.
        """

        os.environ['INSERTNAMEHERE_DIR'] = '/HORSEFEATHERS'
        with self.assertRaises(Error):
            c = config.get_config()

    def test_facilities(self):
        facilities = config.get_facilities()

        self.assertIsInstance(facilities, list)
        for facility in facilities:
            self.assertIsInstance(facility, type)
