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


class JCMTS2CalcTestCase(CalculatorTestCase):
    calculator_class = SCUBA2Calculator

    def test_basic(self):
        self._test_basic(expect)
