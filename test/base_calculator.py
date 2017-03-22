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

from hedwig.compat import string_type
from hedwig.view.calculator import BaseCalculator
from hedwig.type.simple import CalculatorMode, CalculatorValue

from .compat import TestCase


class CalculatorTestCase(TestCase):
    calculator_class = None

    def _test_basic(self, expect):
        # Check we can construct a calculator object.
        self.assertIsInstance(self.calculator_class.get_code(), string_type)

        calc = self.calculator_class(None, 1)
        self.assertIsInstance(calc, BaseCalculator)

        # Check information attributes / methods.
        self.assertIsInstance(calc.version, int)
        self.assertIsInstance(calc.get_name(), string_type)
        self.assertIsInstance(calc.get_extra_context(), dict)

        # Check expected values.
        for (mode, mode_info) in expect.items():
            self.assertTrue(calc.is_valid_mode(mode))
            self.assertIsInstance(calc.get_mode_info(mode), CalculatorMode)

            # Check default input keys for current version: should match
            # input codes.
            version = calc.version
            inputs = calc.get_inputs(mode, version)

            default_input = calc.get_default_input(mode)
            self.assertEqual(
                sorted(default_input.keys()), sorted(x.code for x in inputs))

            # Check inputs and outputs for each mode against expected values.
            for (version, info) in mode_info.items():
                inputs = calc.get_inputs(mode, version)
                for input_ in inputs:
                    self.assertIsInstance(input_, CalculatorValue)
                self.assertEqual(
                    [x.code for x in inputs], info['input'].split())

                outputs = calc.get_outputs(mode, version)
                for output in outputs:
                    self.assertIsInstance(output, CalculatorValue)
                self.assertEqual(
                    [x.code for x in outputs], info['output'].split())
