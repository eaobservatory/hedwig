# Copyright (C) 2015 East Asian Observatory
# All Rights Reserved.
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful,but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc.,51 Franklin
# Street, Fifth Floor, Boston, MA  02110-1301, USA

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from collections import OrderedDict
from unittest import TestCase

from hedwig.error import UserError
from hedwig.facility.jcmt.type import \
    JCMTInstrument, \
    JCMTRequest, JCMTRequestCollection, JCMTRequestTotal, JCMTWeather
from hedwig.type import ResultTable


class JCMTTypeTestCase(TestCase):
    def test_instrument(self):
        options = JCMTInstrument.get_options()
        self.assertIsInstance(options, OrderedDict)

        instruments = set()
        for instrument in (
                JCMTInstrument.SCUBA2,
                JCMTInstrument.HARP,
                JCMTInstrument.RXA3,
                ):
            # Identifiers should be unique integers.
            self.assertIsInstance(instrument, int)
            self.assertNotIn(instrument, instruments)
            instruments.add(instrument)

            # is_valid and get_name should work on these values.
            self.assertTrue(JCMTInstrument.is_valid(instrument))
            self.assertIsInstance(JCMTInstrument.get_name(instrument), unicode)

            # It should also be in the list of options.
            self.assertIn(instrument, options)
            self.assertIsInstance(options[instrument], unicode)

        self.assertFalse(JCMTInstrument.is_valid(0))
        self.assertFalse(JCMTInstrument.is_valid(999))

    def test_weather(self):
        options = JCMTWeather.get_available()
        self.assertIsInstance(options, OrderedDict)

        weathers = set()
        for weather in (
                JCMTWeather.BAND1,
                JCMTWeather.BAND2,
                JCMTWeather.BAND3,
                JCMTWeather.BAND4,
                JCMTWeather.BAND5,
                ):
            # Identifiers should be unique integers.
            self.assertIsInstance(weather, int)
            self.assertNotIn(weather, weathers)
            weathers.add(weather)

            # is_valid and get_name should work on these values.
            self.assertTrue(JCMTWeather.is_valid(weather))
            self.assertIsInstance(JCMTWeather.get_name(weather), unicode)

            # It should also be in the list of options.
            self.assertIn(weather, options)
            self.assertIsInstance(options[weather].name, unicode)

        self.assertFalse(JCMTWeather.is_valid(0))
        self.assertFalse(JCMTWeather.is_valid(999))

    def test_request_collection(self):
        c = JCMTRequestCollection()
        self.assertIsInstance(c, OrderedDict)

        # An empty table should have a table attribute which is false.
        t = c.to_table()
        self.assertIsInstance(t, ResultTable)
        self.assertFalse(t.table)

        total = c.get_total()
        self.assertIsInstance(total, JCMTRequestTotal)
        self.assertEqual(total.total, 0.0)
        self.assertEqual(total.instrument, {})
        self.assertEqual(total.weather, {})

        # Add some rows.
        c[1] = JCMTRequest(1, 0, instrument=1, weather=1, time=10.0)
        c[2] = JCMTRequest(2, 0, instrument=1, weather=1, time=20.0)
        c[3] = JCMTRequest(3, 0, instrument=1, weather=2, time=100.0)

        # The table's table attribute is now true.
        t = c.to_table()
        self.assertIsInstance(t, ResultTable)
        self.assertTrue(t.table)

        # We should have the instrument, but no totals as there is only one.
        self.assertIn(1, t.table)
        self.assertNotIn(0, t.table)

        # Check the weather band times have been added up as expected.
        self.assertEqual(t.table[1], {1: 30.0, 2: 100.0, 0: 130.0})

        # And we should have sensible rows and columns dictionaries.
        self.assertIsInstance(t.rows, OrderedDict)
        self.assertEqual(list(t.rows.keys()), [1])

        self.assertIsInstance(t.columns, OrderedDict)
        self.assertEqual(list(t.columns.keys()),
                         list(JCMTWeather.get_available().keys()))

        # Add data for more instruments.
        c[4] = JCMTRequest(4, 0, instrument=2, weather=2, time=200.0)
        c[5] = JCMTRequest(5, 0, instrument=3, weather=4, time=1000.0)
        t = c.to_table()

        # Check the rows.
        self.assertEqual(set(t.table.keys()), set((0, 1, 2, 3)))
        self.assertEqual(set(t.rows.keys()), set((1, 2, 3)))

        # And check the combined times.
        self.assertEqual(t.table[1], {1: 30.0, 2: 100.0,            0: 130.0})
        self.assertEqual(t.table[2],          {2: 200.0,            0: 200.0})
        self.assertEqual(t.table[3],                    {4: 1000.0, 0: 1000.0})
        self.assertEqual(t.table[0], {1: 30.0, 2: 300.0, 4: 1000.0, 0: 1330.0})

        total = c.get_total()
        self.assertIsInstance(total, JCMTRequestTotal)
        self.assertEqual(total.total, 1330.0)
        self.assertEqual(total.instrument, {1: 130.0, 2: 200.0, 3: 1000.0})
        self.assertEqual(total.weather, {1: 30.0, 2: 300.0, 4: 1000.0})

        # Check conversion to sorted list.
        c[6] = JCMTRequest(6, 0, instrument=2, weather=1, time=500.0)
        sorted_list = c.to_sorted_list()
        self.assertIsInstance(sorted_list, list)
        self.assertEqual(len(sorted_list), 6)
        self.assertEqual(sorted_list[0].id, 1)
        self.assertEqual(sorted_list[1].id, 2)
        self.assertEqual(sorted_list[2].id, 3)
        self.assertEqual(sorted_list[3].id, 6)
        self.assertEqual(sorted_list[4].id, 4)
        self.assertEqual(sorted_list[5].id, 5)

        self.assertEqual(sorted_list[0].instrument, 'SCUBA-2')
        self.assertEqual(sorted_list[1].instrument, 'SCUBA-2')
        self.assertEqual(sorted_list[2].instrument, 'SCUBA-2')
        self.assertEqual(sorted_list[3].instrument, 'HARP')
        self.assertEqual(sorted_list[4].instrument, 'HARP')
        self.assertEqual(sorted_list[5].instrument, 'RxA3')

        self.assertEqual(sorted_list[0].weather, 'Band 1')
        self.assertEqual(sorted_list[1].weather, 'Band 1')
        self.assertEqual(sorted_list[2].weather, 'Band 2')
        self.assertEqual(sorted_list[3].weather, 'Band 1')
        self.assertEqual(sorted_list[4].weather, 'Band 2')
        self.assertEqual(sorted_list[5].weather, 'Band 4')

        self.assertEqual(sorted_list[0].time, 10.0)
        self.assertEqual(sorted_list[1].time, 20.0)
        self.assertEqual(sorted_list[2].time, 100.0)
        self.assertEqual(sorted_list[3].time, 500.0)
        self.assertEqual(sorted_list[4].time, 200.0)
        self.assertEqual(sorted_list[5].time, 1000.0)

        # This result collection isn't valid because instrument=1, weather=1
        # is repeated.
        with self.assertRaisesRegexp(UserError, 'multiple entries'):
            c.validate()

        # Validation should succeed if we remove the offending entry.
        del c[1]
        c.validate()

        # Check the other validation constraints.
        c[1] = JCMTRequest(1, 0, instrument=1, weather=1, time='')
        with self.assertRaisesRegexp(UserError, 'valid number'):
            c.validate()

        c[1] = JCMTRequest(1, 0, instrument=0, weather=1, time=1.0)
        with self.assertRaisesRegexp(UserError, 'Instrument not recognised'):
            c.validate()

        c[1] = JCMTRequest(1, 0, instrument=1, weather=0, time=1.0)
        with self.assertRaisesRegexp(UserError, 'Weather band not recognised'):
            c.validate()
