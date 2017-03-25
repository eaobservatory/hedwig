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

from hedwig.facility.jcmt.calculator_scuba2 import SCUBA2Calculator

from .base_calculator import CalculatorTestCase


expect = {
    SCUBA2Calculator.CALC_TIME: {
        2: {
            'input': 'pos pos_type tau map samp pix850 pix450 wl rms',
            'output': 'time',
        },
        1: {
            'input': 'pos pos_type tau map mf pix850 pix450 wl rms',
            'output': 'time',
        },
    },

    SCUBA2Calculator.CALC_RMS: {
        2: {
            'input': 'pos pos_type tau map samp pix850 pix450 time',
            'output': 'rms_850 rms_450',
        },
        1: {
            'input': 'pos pos_type tau map mf pix850 pix450 time',
            'output': 'rms_850 rms_450',
        },
    },
}


conversions = [
    ('time w/ mf', SCUBA2Calculator.CALC_TIME, {
        1: {
            'map': 'daisy',
            'pos': 65.43,
            'pos_type': 'dec',
            'tau': 0.040,
            'pix850': None,
            'pix450': None,
            'mf': True,
            'wl': 850,
            'rms': 1.5,
        },
        2: {
            'map': 'daisy',
            'pos': 65.43,
            'pos_type': 'dec',
            'tau': 0.040,
            'samp': 'mf',
            'pix850': None,
            'pix450': None,
            'wl': 850,
            'rms': 1.5,
        }
    }),

    ('time w/o mf', SCUBA2Calculator.CALC_TIME, {
        1: {
            'map': 'daisy',
            'pos': 22.22,
            'pos_type': 'zen',
            'tau': 0.080,
            'pix850': 8,
            'pix450': 4,
            'mf': False,
            'wl': 850,
            'rms': 1.5,
        },
        2: {
            'map': 'daisy',
            'pos': 22.22,
            'pos_type': 'zen',
            'tau': 0.080,
            'samp': 'custom',
            'pix850': 8,
            'pix450': 4,
            'wl': 850,
            'rms': 1.5,
        },
    }),

    ('rms w/ mf', SCUBA2Calculator.CALC_RMS, {
        1: {
            'map': 'pong1800',
            'pos': 1.2345,
            'pos_type': 'am',
            'tau': 0.123,
            'pix850': None,
            'pix450': None,
            'mf': True,
            'time': 4.5,
        },
        2: {
            'map': 'pong1800',
            'pos': 1.2345,
            'pos_type': 'am',
            'tau': 0.123,
            'samp': 'mf',
            'pix850': None,
            'pix450': None,
            'time': 4.5,
        },
    }),

    ('rms w/o mf', SCUBA2Calculator.CALC_RMS, {
        1: {
            'map': 'pong900',
            'pos': 72.25,
            'pos_type': 'el',
            'tau': 0.0987,
            'pix850': 13,
            'pix450': 8,
            'mf': False,
            'time': 2.76,
        },
        2: {
            'map': 'pong900',
            'pos': 72.25,
            'pos_type': 'el',
            'tau': 0.0987,
            'samp': 'custom',
            'pix850': 13,
            'pix450': 8,
            'time': 2.76,
        },
    }),
]


class JCMTS2CalcTestCase(CalculatorTestCase):
    calculator_class = SCUBA2Calculator

    def test_basic(self):
        self._test_basic(expect)

    def test_convert_version(self):
        self._test_convert_version(conversions)
