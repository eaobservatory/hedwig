# Copyright (C) 2015-2016 East Asian Observatory
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

from hedwig.compat import string_type
from hedwig.error import UserError
from hedwig.facility.jcmt.type import \
    JCMTAvailable, JCMTAvailableCollection, \
    JCMTInstrument, \
    JCMTRequest, JCMTRequestCollection, JCMTRequestTotal, \
    JCMTReviewerExpertise, \
    JCMTWeather
from hedwig.type.collection import ResultTable

from .compat import TestCase


class JCMTTypeTestCase(TestCase):
    def test_instrument(self):
        options = JCMTInstrument.get_options()
        self.assertIsInstance(options, OrderedDict)

        instruments = set()
        for instrument in (
                JCMTInstrument.HARP,
                JCMTInstrument.ALAIHI,
                JCMTInstrument.UU,
                JCMTInstrument.AWEOWEO,
                JCMTInstrument.KUNTUR,
                ):
            # Identifiers should be unique integers.
            self.assertIsInstance(instrument, int)
            self.assertNotIn(instrument, instruments)
            instruments.add(instrument)

            # is_valid, is_available and get_name should work on these values.
            self.assertTrue(JCMTInstrument.is_valid(instrument))
            self.assertTrue(JCMTInstrument.is_available(instrument))
            instrument_name = JCMTInstrument.get_name(instrument)
            self.assertIsInstance(instrument_name, string_type)

            # It should also be in the list of options.
            self.assertIn(instrument, options)
            self.assertIsInstance(options[instrument], string_type)
            self.assertEqual(options[instrument], instrument_name)

        self.assertFalse(JCMTInstrument.is_valid(0))
        self.assertFalse(JCMTInstrument.is_valid(999))

        # Check set of instruments considered to be available.
        self.assertEqual(set(options.keys()), instruments)

        for instrument in (
                JCMTInstrument.RXA3,
                JCMTInstrument.RXA3M,
                JCMTInstrument.SCUBA2,
                ):
            # Identifiers should be unique integers.
            self.assertIsInstance(instrument, int)
            self.assertNotIn(instrument, instruments)
            instruments.add(instrument)

            # is_valid and get_name should work on these values.
            self.assertTrue(JCMTInstrument.is_valid(instrument))
            self.assertFalse(JCMTInstrument.is_available(instrument))
            instrument_name = JCMTInstrument.get_name(instrument)
            self.assertIsInstance(instrument_name, string_type)

            # It should also not be in the list of options.
            self.assertNotIn(instrument, options)

        self.assertEqual(
            set(JCMTInstrument.get_options(include_unavailable=True).keys()),
            instruments)

    def test_reviewer_expertise(self):
        options = JCMTReviewerExpertise.get_options()
        self.assertIsInstance(options, OrderedDict)

        for expertise in (
                JCMTReviewerExpertise.NON_EXPERT,
                JCMTReviewerExpertise.INTERMEDIATE,
                JCMTReviewerExpertise.EXPERT,
                ):
            self.assertIsInstance(expertise, int)
            self.assertTrue(JCMTReviewerExpertise.is_valid(expertise))

            weight = JCMTReviewerExpertise.get_weight(expertise)
            self.assertIsInstance(weight, int)
            self.assertGreaterEqual(weight, 0)
            self.assertLessEqual(weight, 100)

            name = JCMTReviewerExpertise.get_name(expertise)
            self.assertIsInstance(name, string_type)

            self.assertIn(expertise, options)
            option_name = options.pop(expertise)
            self.assertEqual(option_name, name)

        self.assertFalse(JCMTReviewerExpertise.is_valid(999))
        self.assertFalse(options)

    def test_weather(self):
        options = JCMTWeather.get_available()
        self.assertIsInstance(options, OrderedDict)

        option_names = JCMTWeather.get_options()
        self.assertIsInstance(option_names, OrderedDict)

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
            weather_name = JCMTWeather.get_name(weather)
            self.assertIsInstance(weather_name, string_type)

            # It should also be in the list of options.
            self.assertIn(weather, options)
            self.assertIsInstance(options[weather].name, string_type)
            self.assertEqual(options[weather].name, weather_name)

            self.assertIn(weather, option_names)
            self.assertIsInstance(option_names[weather], string_type)
            self.assertEqual(option_names[weather], weather_name)

        self.assertFalse(JCMTWeather.is_valid(0))
        self.assertFalse(JCMTWeather.is_valid(999))

        # Check set of weathers considered to be available.
        self.assertEqual(set(options.keys()), weathers)

        self.assertEqual(set(JCMTWeather.get_options().keys()), weathers)

        self.assertEqual(
            set(JCMTWeather.get_options(include_unavailable=True).keys()),
            weathers)

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
        self.assertEqual(total.instrument_grouped, {})
        self.assertEqual(total.weather, {})
        self.assertEqual(total.total_non_free, 0.0)

        # Add some rows.
        c[1] = JCMTRequest(1, 0, instrument=1, ancillary=0,
                           weather=1, time=10.0)
        c[2] = JCMTRequest(2, 0, instrument=1, ancillary=0,
                           weather=1, time=20.0)
        c[3] = JCMTRequest(3, 0, instrument=1, ancillary=0,
                           weather=2, time=100.0)

        # The table's table attribute is now true.
        t = c.to_table()
        self.assertIsInstance(t, ResultTable)
        self.assertTrue(t.table)

        # We should have the instrument, but no totals as there is only one.
        self.assertIn((1, 0), t.table)
        self.assertNotIn(0, t.table)

        # Check the weather band times have been added up as expected.
        self.assertEqual(t.table[(1, 0)], {1: 30.0, 2: 100.0, None: 130.0})

        # And we should have sensible rows and columns dictionaries.
        self.assertIsInstance(t.rows, OrderedDict)
        self.assertEqual(list(t.rows.keys()), [(1, 0)])

        self.assertIsInstance(t.columns, OrderedDict)
        self.assertEqual(list(t.columns.keys()),
                         list(JCMTWeather.get_available().keys()))

        # Add data for more instruments.
        c[4] = JCMTRequest(4, 0, instrument=2, ancillary=0,
                           weather=2, time=200.0)
        c[5] = JCMTRequest(5, 0, instrument=4, ancillary=0,
                           weather=5, time=1000.0)
        t = c.to_table()

        # Check the rows.
        self.assertEqual(
            set(t.table.keys()), set((None, (1, 0), (2, 0), (4, 0))))
        self.assertEqual(
            set(t.rows.keys()), set(((1, 0), (2, 0), (4, 0))))

        # And check the combined times.
        self.assertEqual(
            t.table[(1, 0)], {1: 30.0, 2: 100.0,            None: 130.0})
        self.assertEqual(
            t.table[(2, 0)],          {2: 200.0,            None: 200.0})
        self.assertEqual(
            t.table[(4, 0)],                    {5: 1000.0, None: 1000.0})
        self.assertEqual(
            t.table[None],   {1: 30.0, 2: 300.0, 5: 1000.0, None: 1330.0})

        total = c.get_total(include_unavailable_instrument=True)
        self.assertIsInstance(total, JCMTRequestTotal)
        self.assertEqual(total.total, 1330.0)
        self.assertEqual(
            total.instrument, {(1, 0): 130.0, (2, 0): 200.0, (4, 0): 1000.0})
        self.assertEqual(
            total.instrument_total, {1: 130.0, 2: 200.0, 4: 1000.0})
        self.assertEqual(
            total.instrument_grouped,
            {1: {0: 130.0}, 2: {0: 200.0}, 4: {0: 1000.0}})
        self.assertEqual(total.weather, {1: 30.0, 2: 300.0, 5: 1000.0})
        self.assertEqual(total.total_non_free, 330.0)

        # Check conversion to sorted list.
        c[6] = JCMTRequest(6, 0, instrument=2, ancillary=0,
                           weather=1, time=500.0)
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
        self.assertEqual(sorted_list[5].instrument, 'RxA3m')

        self.assertEqual(sorted_list[0].weather, 'Band 1')
        self.assertEqual(sorted_list[1].weather, 'Band 1')
        self.assertEqual(sorted_list[2].weather, 'Band 2')
        self.assertEqual(sorted_list[3].weather, 'Band 1')
        self.assertEqual(sorted_list[4].weather, 'Band 2')
        self.assertEqual(sorted_list[5].weather, 'Band 5')

        self.assertEqual(sorted_list[0].time, 10.0)
        self.assertEqual(sorted_list[1].time, 20.0)
        self.assertEqual(sorted_list[2].time, 100.0)
        self.assertEqual(sorted_list[3].time, 500.0)
        self.assertEqual(sorted_list[4].time, 200.0)
        self.assertEqual(sorted_list[5].time, 1000.0)

        # This result collection isn't valid because instrument=1, weather=1
        # is repeated.
        with self.assertRaisesRegex(UserError, 'multiple entries'):
            c.validate()

        # Validation should succeed if we remove the offending entry.
        del c[1]
        c.validate()

        # Check the other validation constraints.
        c[1] = JCMTRequest(1, 0, instrument=1, ancillary=0,
                           weather=1, time='')
        with self.assertRaisesRegex(UserError, 'valid number'):
            c.validate()

        c[1] = JCMTRequest(1, 0, instrument=0, ancillary=0,
                           weather=1, time=1.0)
        with self.assertRaisesRegex(UserError, 'Instrument not recognised'):
            c.validate()

        c[1] = JCMTRequest(1, 0, instrument=1, ancillary=999,
                           weather=1, time=1.0)
        with self.assertRaisesRegex(
                UserError, 'Ancillary instrument not recognised'):
            c.validate()

        c[1] = JCMTRequest(1, 0, instrument=1,
                           ancillary=1, weather=1, time=1.0)
        with self.assertRaisesRegex(
                UserError, 'Ancillary not permitted for this instrument'):
            c.validate()

        c[1] = JCMTRequest(1, 0, instrument=1, ancillary=0,
                           weather=0, time=1.0)
        with self.assertRaisesRegex(UserError, 'Weather band not recognised'):
            c.validate()

    def test_available_collection(self):
        c = JCMTAvailableCollection()

        c[1001] = JCMTAvailable(1001, 100, 2, 10.0)
        c[1002] = JCMTAvailable(1002, 100, 5, 15.0)

        # Test the "get_total" method.
        total = c.get_total()
        self.assertIsInstance(total, JCMTRequestTotal)
        self.assertEqual(total.total, 25)
        self.assertEqual(total.weather, {2: 10.0, 5: 15.0})
        self.assertEqual(total.instrument, {})
        self.assertEqual(total.total_non_free, 10)

        # Test the "validate" method.
        c.validate()

        c[1003] = JCMTAvailable(1003, 100, 5, 20.0)

        with self.assertRaisesRegex(UserError, 'There are multiple entries'):
            c.validate()
