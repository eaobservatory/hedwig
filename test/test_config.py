# Copyright (C) 2014 Science and Technology Facilities Council.
# Copyright (C) 2015-2021 East Asian Observatory.
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

from collections import OrderedDict
import os

try:
    from configparser import ConfigParser
except ImportError:
    from ConfigParser import SafeConfigParser as ConfigParser

from hedwig import config
from hedwig.error import Error
from hedwig.db.control import Database
from hedwig.facility.jcmt.control import JCMTPart
from hedwig.type.simple import FacilityInfo

from .dummy_config import DummyConfigTestCase


class ConfigTestCase(DummyConfigTestCase):
    def test_countries(self):
        c = config.get_countries()

        # Check we got a sensible-looking dictionary of countries.
        self.assertIsInstance(c, OrderedDict)
        self.assertLess(len(c), 300)
        self.assertGreater(len(c), 200)
        self.assertIn('AX', c)
        self.assertNotIn('BX', c)
        self.assertIn('CX', c)

        # Try countries with and without "common_name" records.
        self.assertEqual(c['TW'], 'Taiwan')
        self.assertEqual(c['JP'], 'Japan')

        # Test country with non-ASCII character in name.
        self.assertEqual(c['CW'], 'Cura\u00e7ao')

        # Check we get the same object if we call the function again.
        cc = config.get_countries()
        self.assertIs(cc, c)

    def test_database_config(self):
        c = config.get_config()

        self.assertIsInstance(c, ConfigParser)

        self.assertTrue(c.has_section('database'))
        self.assertTrue(c.has_option('database', 'url'))

    def test_home_var(self):
        """
        Test that we get an error if the file doesn't exists.

        Also checks that the environment variable is being read.
        """

        os.environ['HEDWIG_DIR'] = '/HORSEFEATHERS'
        with self.assertRaises(Error):
            c = config.get_config()

    def test_get_facility(self):
        # Default facility from template configuration file.
        self.assertEqual(
            [x.name for x in config.get_facilities(db=()).values()],
            ['Generic Facility'])

        # Facility by plain class name.
        self.assertEqual(
            [x.name for x in config.get_facilities(
                db=(), facility_spec='JCMT').values()],
            ['JCMT'])

        # Facilities by full module and class name.
        self.assertEqual(
            [x.name for x in config.get_facilities(
                db=(), facility_spec='hedwig.facility.generic.view.Generic,'
                'hedwig.facility.jcmt.view.JCMT').values()],
            ['Generic Facility', 'JCMT'])

    def test_get_database(self):
        database_url = 'sqlite:///:memory:'

        # Default database via template configuration file.
        db = config.get_database(database_url=database_url)
        self.assertEqual(db.__class__.__name__, 'CombinedDatabase')
        self.assertIsInstance(db, Database)
        self.assertNotIsInstance(db, JCMTPart)

        # Get database via plain facility name.
        db = config.get_database(database_url=database_url,
                                 facility_spec='JCMT')
        self.assertEqual(db.__class__.__name__, 'CombinedDatabase')
        self.assertIsInstance(db, Database)
        self.assertIsInstance(db, JCMTPart)

        # Get database via plain facility name.
        db = config.get_database(
            database_url=database_url,
            facility_spec='hedwig.facility.jcmt.view.JCMT')
        self.assertEqual(db.__class__.__name__, 'CombinedDatabase')
        self.assertIsInstance(db, Database)
        self.assertIsInstance(db, JCMTPart)

    def test_facilities(self):
        facilities = config.get_facilities(db=())

        self.assertIsInstance(facilities, OrderedDict)
        for facility in facilities.values():
            self.assertIsInstance(facility, FacilityInfo)
