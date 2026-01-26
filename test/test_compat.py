# Copyright (C) 2016-2026 East Asian Observatory
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

from hedwig.compat import char, first_value, iter_items, move_to_end, \
    split_version, string_type

from .compat import TestCase


class CompatTestCase(TestCase):
    def test_char(self):
        c = char(65)
        self.assertIsInstance(c, string_type)
        self.assertEqual(c, 'A')

    def test_split_version(self):
        version = split_version('5.2.8')
        self.assertIsInstance(version, tuple)
        self.assertEqual(len(version), 3)
        self.assertIsInstance(version[0], int)
        self.assertIsInstance(version[1], int)
        self.assertIsInstance(version[2], int)
        self.assertEqual(version, (5, 2, 8))

    def test_first_value(self):
        self.assertEqual(first_value({4: 8}), 8)

        self.assertEqual(first_value(OrderedDict(((1, 2), (3, 4), (5, 6)))),
                         2)

        with self.assertRaises(IndexError):
            first_value({})

    def test_iter_items(self):
        d = OrderedDict(((1, 'a'), (2, 'b'), (3, 'c')))
        iterator = iter_items(d)

        l = []
        while True:
            try:
                l.append(next(iterator))
            except StopIteration:
                break

        self.assertEqual(l, [(1, 'a'), (2, 'b'), (3, 'c')])

    def test_move_to_end(self):
        d = OrderedDict(((1, 'a'), (2, 'b'), (3, 'c')))

        self.assertEqual(list(iter_items(d)), [(1, 'a'), (2, 'b'), (3, 'c')])

        move_to_end(d, 2)

        self.assertEqual(list(iter_items(d)), [(1, 'a'), (3, 'c'), (2, 'b')])
