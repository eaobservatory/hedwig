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

from hedwig.facility.jcmt.calculator_heterodyne import HeterodyneCalculator

from .base_calculator import CalculatorTestCase


expect = {
    HeterodyneCalculator.CALC_TIME: {
        3: {
            'input':
                'rx res res_unit if side sb sep_pol cont '
                'species trans freq rv rv_sys pos pos_type tau '
                'mm sw n_pt sep_off dim_x dim_y dx dy basket rms',
            'output': 'elapsed',
        },
        2: {
            'input':
                'rx res res_unit sb cont dual_pol '
                'species trans freq rv rv_sys pos pos_type tau '
                'mm sw n_pt sep_off dim_x dim_y dx dy basket rms',
            'output': 'elapsed',
        },
        1: {
            'input':
                'rx res res_unit sb cont dual_pol freq pos pos_type tau '
                'mm sw n_pt sep_off dim_x dim_y dx dy basket rms',
            'output': 'elapsed',
        },
    },

    HeterodyneCalculator.CALC_RMS_FROM_ELAPSED_TIME: {
        3: {
            'input':
                'rx res res_unit if side sb sep_pol  cont '
                'species trans freq rv rv_sys pos pos_type tau '
                'mm sw n_pt sep_off dim_x dim_y dx dy basket elapsed',
            'output': 'rms',
        },
        2: {
            'input':
                'rx res res_unit sb cont dual_pol '
                'species trans freq rv rv_sys pos pos_type tau '
                'mm sw n_pt sep_off dim_x dim_y dx dy basket elapsed',
            'output': 'rms',
        },
        1: {
            'input':
                'rx res res_unit sb cont dual_pol freq pos pos_type tau '
                'mm sw n_pt sep_off dim_x dim_y dx dy basket elapsed',
            'output': 'rms',
        },
    },

    HeterodyneCalculator.CALC_RMS_FROM_INT_TIME: {
        3: {
            'input':
                'rx res res_unit if side sb sep_pol cont '
                'species trans freq rv rv_sys pos pos_type tau '
                'mm sw n_pt sep_off dim_x dim_y dx dy basket int_time',
            'output': 'rms elapsed',
        },
        2: {
            'input':
                'rx res res_unit sb cont dual_pol '
                'species trans freq rv rv_sys pos pos_type tau '
                'mm sw n_pt sep_off dim_x dim_y dx dy basket int_time',
            'output': 'rms elapsed',
        },
        1: {
            'input':
                'rx res res_unit sb cont dual_pol freq pos pos_type tau '
                'mm sw n_pt sep_off dim_x dim_y dx dy basket int_time',
            'output': 'rms elapsed',
        },
    },
}


class JCMTHetCalcTestCase(CalculatorTestCase):
    calculator_class = HeterodyneCalculator

    def test_basic(self):
        self._test_basic(expect)
