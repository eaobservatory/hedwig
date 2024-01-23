# Copyright (C) 2015-2024 East Asian Observatory
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

from io import BytesIO

from hedwig.error import Error
from hedwig.util import ClosingMultiple, FormatMaxDP, FormatSigFig, \
    is_list_like, list_in_blocks, list_in_ranges, lower_except_abbr, \
    matches_constraint

from .compat import TestCase


class UtilTest(TestCase):
    def test_closing_multiple(self):
        with ClosingMultiple() as closer:
            self.assertIsInstance(closer, ClosingMultiple)

            f_1 = closer(BytesIO())
            self.assertIsInstance(f_1, BytesIO)
            self.assertFalse(f_1.closed)

            f_2 = closer(BytesIO())
            self.assertIsInstance(f_2, BytesIO)
            self.assertFalse(f_2.closed)

        self.assertTrue(f_1.closed)
        self.assertTrue(f_1.closed)

    def test_list_in_blocks(self):
        self.assertEqual(list(list_in_blocks(range(0, 3), 5)),
                         [[0, 1, 2]])

        self.assertEqual(list(list_in_blocks(range(0, 10), 5)),
                         [[0, 1, 2, 3, 4], [5, 6, 7, 8, 9]])

        self.assertEqual(list(list_in_blocks(range(0, 12), 5)),
                         [[0, 1, 2, 3, 4], [5, 6, 7, 8, 9], [10, 11]])

        self.assertEqual(list(list_in_blocks([], 5)),
                         [])

    def test_list_in_ranges(self):
        self.assertEqual(list_in_ranges(
            []),
            ([], []))

        self.assertEqual(list_in_ranges(
            [101]),
            ([], [101]))

        self.assertEqual(list_in_ranges(
            [101, 102]),
            ([], [101, 102]))

        self.assertEqual(list_in_ranges(
            [103, 101, 102]),
            ([(101, 103)], []))

        self.assertEqual(list_in_ranges(
            [103, 101, 104, 102, 100]),
            ([(100, 104)], []))

        self.assertEqual(list_in_ranges(
            [103, 101, 104, 102, 100, 90, 120]),
            ([(100, 104)], [90, 120]))

        self.assertEqual(list_in_ranges(
            [103, 101, 104, 102, 100, 90, 120, 91, 122]),
            ([(100, 104)], [90, 91, 120, 122]))

        self.assertEqual(list_in_ranges(
            [103, 101, 104, 102, 100, 90, 120, 91, 122, 93, 121]),
            ([(100, 104), (120, 122)], [90, 91, 93]))

    def test_is_list_like(self):
        self.assertTrue(is_list_like([1, 2]))
        self.assertTrue(is_list_like((3, 4)))
        self.assertTrue(is_list_like(set((5, 6))))
        self.assertFalse(is_list_like(7))
        self.assertFalse(is_list_like('8'))
        self.assertFalse(is_list_like(None))

    def test_lower_except_abbr(self):
        self.assertEqual(lower_except_abbr('A TLA Review'), 'a TLA review')

    def test_matches_constraint(self):
        self.assertTrue(matches_constraint(1, None))
        self.assertTrue(matches_constraint(2, None))
        self.assertTrue(matches_constraint(3, None))

        self.assertTrue(matches_constraint(1, 1))
        self.assertFalse(matches_constraint(2, 1))
        self.assertFalse(matches_constraint(3, 1))

        self.assertTrue(matches_constraint(1, (1, 2)))
        self.assertTrue(matches_constraint(2, (1, 2)))
        self.assertFalse(matches_constraint(3, (1, 2)))

    def test_sig_fig(self):
        fmt = FormatSigFig(3)
        self.assertEqual(fmt.format(123456789.0), '123456789')
        self.assertEqual(fmt.format(12345678.9), '12345679')
        self.assertEqual(fmt.format(1234567.890), '1234568')
        self.assertEqual(fmt.format(123456.7890), '123457')
        self.assertEqual(fmt.format(12345.67890), '12346')
        self.assertEqual(fmt.format(1234.567890), '1235')
        self.assertEqual(fmt.format(123.4567890), '123')
        self.assertEqual(fmt.format(12.34567890), '12.3')
        self.assertEqual(fmt.format(1.234567890), '1.23')
        self.assertEqual(fmt.format(0.1234567890), '0.123')
        self.assertEqual(fmt.format(0.01234567890), '0.0123')
        self.assertEqual(fmt.format(0.001234567890), '0.00123')
        self.assertEqual(fmt.format(0.0001234567890), '0.000123')
        self.assertEqual(fmt.format(0.00001234567890), '0.0000123')
        self.assertEqual(fmt.format(0.000001234567890), '0.00000123')
        self.assertEqual(fmt.format(0.0000001234567890), '0.000000123')
        self.assertEqual(fmt.format(0.00000001234567890), '0.000000012')
        self.assertEqual(fmt.format(0.000000001234567890), '0.000000001')
        self.assertEqual(fmt.format(0.0000000001234567890), '0.000000000')

        fmt = FormatSigFig(2, 1, 6)
        self.assertEqual(fmt.format(1000000), '1000000.0')
        self.assertEqual(fmt.format(0.11111), '0.11')
        self.assertEqual(fmt.format(0.0000011111), '0.000001')

        self.assertEqual(fmt.format(-1000000), '-1000000.0')
        self.assertEqual(fmt.format(-0.11111), '-0.11')
        self.assertEqual(fmt.format(-0.0000011111), '-0.000001')

    def test_max_dp(self):
        with self.assertRaisesRegex(Error, 'number of digits must be'):
            fmt = FormatMaxDP(0)

        fmt = FormatMaxDP(3)
        self.assertEqual(fmt.format(123.456789), '123.457')
        self.assertEqual(fmt.format(123.4), '123.4')
        self.assertEqual(fmt.format(120), '120')
