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

from hedwig.facility.ukirt.calculator_imag_phot import ImagPhotCalculator

from .base_calculator import CalculatorTestCase


expect = {
    ImagPhotCalculator.CALC_TIME: {
        1: {
            'input': 'inst filt type am sky seeing aper mag snr',
            'output': 'int_time',
        },
    },

    ImagPhotCalculator.CALC_MAG: {
        1: {
            'input': 'inst filt type am sky seeing aper int_time snr',
            'output': 'mag',
        },
    },

    ImagPhotCalculator.CALC_SNR: {
        1: {
            'input': 'inst filt type am sky seeing aper int_time mag',
            'output': 'snr',
        },
    },
}


class UKIRTIPCalcTestCase(CalculatorTestCase):
    calculator_class = ImagPhotCalculator

    def test_basic(self):
        self._test_basic(expect)
