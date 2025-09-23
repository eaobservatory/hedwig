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
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

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

    def test_memo_cache(self):
        @config.MemoCache()
        def func(x):
            return [x * 2]

        x2 = func(2)
        self.assertIsInstance(x2, list)
        self.assertEqual(x2[0], 4)

        x3 = func(3)
        self.assertIsInstance(x3, list)
        self.assertEqual(x3[0], 6)
        self.assertIsNot(x3, x2)

        x2b = func(2)
        self.assertIs(x2b, x2)

        x3b = func(3)
        self.assertIs(x3b, x3)

        self.assertEqual(
            list(sorted(config.MemoCache.instances[-1].cache.keys())),
            [(2,), (3,)])

        config.MemoCache.clear_all()

        x2c = func(2)
        self.assertIsNot(x2c, x2)
        self.assertIsInstance(x2c, list)
        self.assertEqual(x2c[0], 4)

        class DummyID(object):
            n_call = 0

            def __init__(self, id_):
                self._mem_id = id_

            def meth(self, num):
                DummyID.n_call += 1
                return [self._mem_id * num]

        dummy1 = DummyID(1)
        dummy2 = DummyID(2)

        @config.MemoCache()
        def func2(obj, num):
            return obj.meth(num)

        ans1 = func2(dummy1, 4)

        self.assertEqual(ans1[0], 4)
        self.assertEqual(DummyID.n_call, 1)

        ans2 = func2(dummy2, 4)

        self.assertEqual(ans2[0], 8)
        self.assertEqual(DummyID.n_call, 2)

        ans3 = func2(dummy2, 4)

        self.assertIs(ans3, ans2)
        self.assertEqual(DummyID.n_call, 2)

        self.assertEqual(
            list(sorted(config.MemoCache.instances[-1].cache.keys())),
            [(1, 4), (2, 4)])
