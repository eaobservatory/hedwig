# Copyright (C) 2017 East Asian Observatory
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
from hedwig.facility.ukirt.type import \
    UKIRTInstrument, \
    UKIRTRequest, UKIRTRequestCollection, UKIRTRequestTotal

from .compat import TestCase


class UKIRTTypeTestCase(TestCase):
    def test_instrument(self):
        options = UKIRTInstrument.get_options()
        self.assertIsInstance(options, OrderedDict)

        self.assertGreater(len(options), 2)

        for (instrument, instrument_name) in options.items():
            self.assertIsInstance(instrument, int)
            self.assertIsInstance(instrument_name, string_type)
            self.assertTrue(UKIRTInstrument.is_valid(instrument))

        self.assertFalse(UKIRTInstrument.is_valid(0))
        self.assertFalse(UKIRTInstrument.is_valid(999))

    def test_request_collection(self):
        c = UKIRTRequestCollection()
        self.assertIsInstance(c, OrderedDict)

        # Add some rows to the collection.
        c[1] = UKIRTRequest(1, 0, instrument=UKIRTInstrument.WFCAM, time=2.0)
        c[2] = UKIRTRequest(2, 0, instrument=UKIRTInstrument.UFTI, time=5.0)

        c.validate()

        c[3] = UKIRTRequest(3, 0, instrument=999, time=6.0)
        with self.assertRaisesRegex(UserError, 'Instrument not recognised'):
            c.validate()

        c[3] = UKIRTRequest(3, 0, instrument=UKIRTInstrument.WFCAM, time=6.0)
        with self.assertRaisesRegex(UserError, 'multiple entries'):
            c.validate()

        c[3] = UKIRTRequest(3, 0, instrument=UKIRTInstrument.UIST, time='one')
        with self.assertRaisesRegex(UserError, 'time as a valid number'):
            c.validate()

        del c[3]

        # Test the `to_sorted_list` method.
        l = c.to_sorted_list()
        self.assertIsInstance(l, list)
        self.assertEqual(len(l), 2)

        self.assertEqual(l[0].id, 1)
        self.assertEqual(l[0].instrument, 'WFCAM')
        self.assertEqual(l[0].time, 2.0)

        self.assertEqual(l[1].id, 2)
        self.assertEqual(l[1].time, 5.0)

        # Test the `get_total` method.
        t = c.get_total()
        self.assertIsInstance(t, UKIRTRequestTotal)

        self.assertEqual(t.total, 7.0)
        self.assertEqual(t.instrument, {
            UKIRTInstrument.WFCAM: 2.0,
            UKIRTInstrument.UFTI: 5.0})
